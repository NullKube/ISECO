# ai_engine/feasibility.py
from datetime import datetime, timedelta
from ai_engine.forecast import get_monthly_averages, forecast_savings_ml
from expenses.models import Expense


def check_goal_feasibility(goal, competing_goals=None, user=None):
    """
    Check if a SINGLE goal is feasible by its deadline, considering other locked-in goals.

    Args:
        goal: Goal object to check
        competing_goals: List of Goal objects with LOCKED deadlines (already approved adjustments)
        user: User object

    Returns:
        {
            'is_feasible': bool,
            'months_left': int,
            'required_monthly': float,
            'actual_monthly': float,
            'reason': str,
            'cumulative_needed': float,
            'cumulative_available': float
        }
    """
    today = datetime.now().date()

    # Calculate months remaining for this goal
    months_left = max(1, (goal.deadline.year - today.year) * 12 + (goal.deadline.month - today.month))

    # Get user's monthly savings
    ma = get_monthly_averages(user=user, months=3)
    actual_monthly_savings = ma.get('monthly_savings', 0)

    # Get forecast data
    forecast_data = forecast_savings_ml(months_ahead=months_left, user=user)
    forecast_list = forecast_data.get('forecast', [])

    # Calculate amount remaining for THIS goal
    remaining_this_goal = max(0.0, goal.target_amount - goal.amount_saved)
    required_monthly_this = remaining_this_goal / months_left if months_left > 0 else remaining_this_goal

    # Calculate competing goals requirements (already locked-in)
    competing_monthly = 0
    if competing_goals:
        for other_goal in competing_goals:
            other_remaining = max(0, other_goal.target_amount - other_goal.amount_saved)
            other_months = max(1, (other_goal.deadline.year - today.year) * 12 + (other_goal.deadline.month - today.month))
            competing_monthly += other_remaining / other_months

    # Total required monthly
    total_required_monthly = required_monthly_this + competing_monthly

    # Calculate cumulative savings available using forecast
    cumulative_available = 0
    if forecast_list:
        for i in range(min(months_left, len(forecast_list))):
            cumulative_available += forecast_list[i].get('predicted_monthly_savings', 0)
    else:
        cumulative_available = actual_monthly_savings * months_left

    # Calculate cumulative needed
    cumulative_needed = total_required_monthly * months_left

    # Check feasibility
    is_feasible = cumulative_available >= cumulative_needed

    if is_feasible:
        reason = f"✅ Achievable! Surplus: ₹{round(cumulative_available - cumulative_needed, 2):,}"
    else:
        shortfall = cumulative_needed - cumulative_available
        reason = f"❌ Shortfall: ₹{round(shortfall, 2):,}. Deadline needs to be extended."

    return {
        'is_feasible': is_feasible,
        'months_left': months_left,
        'required_monthly': round(required_monthly_this, 2),
        'actual_monthly': round(actual_monthly_savings, 2),
        'reason': reason,
        'cumulative_needed': round(cumulative_needed, 2),
        'cumulative_available': round(cumulative_available, 2),
        'shortfall': round(max(0, cumulative_needed - cumulative_available), 2)
    }


def find_next_feasible_date(goal, competing_goals=None, user=None, max_months_ahead=36):
    """
    Find the earliest date when a goal becomes feasible, given competing locked-in goals.

    Args:
        goal: Goal object
        competing_goals: List of locked-in goals
        user: User object
        max_months_ahead: Max months to check ahead

    Returns:
        {
            'feasible_date': date or None,
            'months_delay': int,
            'reason': str
        }
    """
    today = datetime.now().date()
    ma = get_monthly_averages(user=user, months=3)
    actual_monthly = ma.get('monthly_savings', 0)

    # Get long-term forecast
    forecast_data = forecast_savings_ml(months_ahead=max_months_ahead, user=user)
    forecast_list = forecast_data.get('forecast', [])

    remaining_this = max(0, goal.target_amount - goal.amount_saved)

    # Calculate competing monthly requirement
    competing_monthly = 0
    if competing_goals:
        for og in competing_goals:
            og_remaining = max(0, og.target_amount - og.amount_saved)
            og_months = max(1, (og.deadline.year - today.year) * 12 + (og.deadline.month - today.month))
            competing_monthly += og_remaining / og_months

    # Try each month ahead
    for months_ahead in range(1, max_months_ahead + 1):
        test_deadline = goal.deadline + timedelta(days=30 * months_ahead)
        months_until_test = max(1, (test_deadline.year - today.year) * 12 + (test_deadline.month - today.month))

        required_monthly_test = remaining_this / months_until_test if months_until_test > 0 else remaining_this
        total_monthly_needed = required_monthly_test + competing_monthly

        # Get cumulative forecast for test period
        cumulative_test = 0
        if forecast_list:
            for i in range(min(months_until_test, len(forecast_list))):
                cumulative_test += forecast_list[i].get('predicted_monthly_savings', 0)
        else:
            cumulative_test = actual_monthly * months_until_test

        cumulative_needed_test = total_monthly_needed * months_until_test

        if cumulative_test >= cumulative_needed_test:
            return {
                'feasible_date': test_deadline,
                'months_delay': months_ahead,
                'reason': f"Feasible by shifting {months_ahead} months. Surplus: ₹{round(cumulative_test - cumulative_needed_test, 2):,}"
            }

    # No feasible date found
    return {
        'feasible_date': None,
        'months_delay': max_months_ahead,
        'reason': f"Even at {max_months_ahead} months extension, goal may not be feasible. Consider increasing income or reducing target."
    }


def get_next_goal_to_check(user=None, exclude_ids=None):
    """
    Get next goal to check for feasibility cascade.

    Sort by:
    1. Priority (highest first, i.e., priority 10 before priority 1)
    2. Amount remaining (smallest first)

    Args:
        user: User object
        exclude_ids: List of goal IDs already checked/approved

    Returns:
        Goal object or None
    """
    from goals.models import Goal

    if exclude_ids is None:
        exclude_ids = []

    # Get active goals, exclude those already checked
    goals = Goal.objects.filter(
        status='active',
        user=user
    ).exclude(
        pk__in=exclude_ids
    ).order_by('-priority', 'amount_remaining')  # Highest priority first, then smallest amount

    return goals.first()


def get_cascade_suggestion(new_goal, user=None):
    """
    Check if a newly created goal is feasible. If not, suggest next feasible date.
    This is the FIRST step in the cascade - checking the new goal itself.

    Returns:
        {
            'goal_id': int,
            'goal_name': str,
            'is_feasible': bool,
            'suggestion': {
                'new_deadline': date or None,
                'months_delay': int,
                'reason': str
            } or None,
            'next_goal_to_check': Goal object or None
        }
    """
    from goals.models import Goal

    # Get other active goals (excluding this new one) with ORIGINAL deadlines (not yet adjusted in cascade)
    # In cascade, we only consider already-saved goals
    other_active = Goal.objects.filter(
        status='active',
        user=user
    ).exclude(pk=new_goal.pk)

    # Check feasibility of new goal with existing goals
    feasibility = check_goal_feasibility(new_goal, competing_goals=list(other_active), user=user)

    if feasibility['is_feasible']:
        return {
            'goal_id': new_goal.id,
            'goal_name': new_goal.name,
            'is_feasible': True,
            'suggestion': None,
            'next_goal_to_check': None  # No cascade needed
        }
    else:
        # Find next feasible date
        next_feasible = find_next_feasible_date(new_goal, competing_goals=list(other_active), user=user)

        return {
            'goal_id': new_goal.id,
            'goal_name': new_goal.name,
            'is_feasible': False,
            'suggestion': {
                'new_deadline': next_feasible['feasible_date'].strftime('%Y-%m-%d') if next_feasible['feasible_date'] else None,
                'months_delay': next_feasible['months_delay'],
                'reason': next_feasible['reason']
            },
            'next_goal_to_check': None  # No cascade needed for new goal
        }


def get_cascade_for_existing_goals(approved_goal_id, user=None, checked_goal_ids=None):
    """
    After a goal's deadline is approved/adjusted, check OTHER goals for feasibility impact.

    This triggers the cascade: check next highest-priority goal, see if it's still feasible,
    and suggest adjustment if needed.

    Args:
        approved_goal_id: ID of goal that was just approved with new deadline
        user: User object
        checked_goal_ids: List of goal IDs already processed in this cascade

    Returns:
        {
            'goal_to_check': Goal object or None,
            'feasibility': {...},
            'suggestion': {...} or None,
            'cascade_complete': bool
        }
    """
    from goals.models import Goal

    if checked_goal_ids is None:
        checked_goal_ids = []

    # Add approved goal to checked list
    checked_goal_ids = list(checked_goal_ids) + [approved_goal_id]

    # Get all locked-in goals (those already checked and approved in this cascade)
    locked_goals = Goal.objects.filter(pk__in=checked_goal_ids, user=user)

    # Find next goal to check (highest priority, then smallest amount)
    remaining_goals = Goal.objects.filter(
        status='active',
        user=user
    ).exclude(pk__in=checked_goal_ids).order_by('-priority', 'amount_remaining')

    next_goal = remaining_goals.first()

    if not next_goal:
        # Cascade complete
        return {
            'goal_to_check': None,
            'feasibility': None,
            'suggestion': None,
            'cascade_complete': True,
            'checked_ids': checked_goal_ids
        }

    # Check feasibility of next goal considering locked-in goals
    feasibility = check_goal_feasibility(next_goal, competing_goals=list(locked_goals), user=user)

    if feasibility['is_feasible']:
        # This goal is still feasible, no suggestion needed, continue cascade
        return {
            'goal_to_check': next_goal,
            'feasibility': feasibility,
            'suggestion': None,
            'cascade_complete': False,
            'checked_ids': checked_goal_ids
        }
    else:
        # This goal needs adjustment
        next_feasible = find_next_feasible_date(next_goal, competing_goals=list(locked_goals), user=user)

        return {
            'goal_to_check': next_goal,
            'feasibility': feasibility,
            'suggestion': {
                'new_deadline': next_feasible['feasible_date'].strftime('%Y-%m-%d') if next_feasible['feasible_date'] else None,
                'months_delay': next_feasible['months_delay'],
                'reason': next_feasible['reason']
            },
            'cascade_complete': False,
            'checked_ids': checked_goal_ids
        }


# =============================================================================
# GOAL FEASIBILITY FUNCTIONS (for compatibility with existing imports)
# =============================================================================

def goal_feasibility(goal, user=None):
    """
    Check if a single goal is feasible by its deadline.
    This is the main function used by templates and views.

    Args:
        goal: Goal object
        user: User object

    Returns:
        {
            'possible': bool,
            'months_left': int,
            'required_per_month': float,
            'monthly_savings': float,
            'reason': str,
            'total_required': float,
            'shortfall': float
        }
    """
    from goals.models import Goal

    # Get competing goals (other active goals for this user)
    competing_goals = list(Goal.objects.filter(
        status='active',
        user=user
    ).exclude(pk=goal.pk))

    # Use check_goal_feasibility
    result = check_goal_feasibility(goal, competing_goals=competing_goals, user=user)

    return {
        'possible': result['is_feasible'],
        'months_left': result['months_left'],
        'required_per_month': result['required_monthly'],
        'monthly_savings': result['actual_monthly'],
        'reason': result['reason'],
        'total_required': result['cumulative_needed'],
        'shortfall': result.get('shortfall', 0)
    }


def multi_goal_feasibility(goals, user=None):
    """
    Check feasibility of multiple goals together.

    Args:
        goals: QuerySet of Goal objects
        user: User object

    Returns:
        {
            'feasible': bool,
            'surplus': float,
            'surplus_abs': float,
            'monthly_savings': float,
            'total_weighted_requirement': float,
            'reason': str,
            'goal_breakdown': list
        }
    """
    from goals.models import Goal

    goals_list = list(goals) if not isinstance(goals, list) else goals

    if not goals_list:
        return {
            'feasible': True,
            'surplus': 0,
            'surplus_abs': 0,
            'monthly_savings': 0,
            'total_weighted_requirement': 0,
            'reason': 'No goals to analyze',
            'goal_breakdown': []
        }

    # Get user's monthly savings
    ma = get_monthly_averages(user=user, months=3)
    monthly_savings = ma.get('monthly_savings', 0)

    today = datetime.now().date()
    goal_breakdown = []
    total_monthly_needed = 0

    # Sort goals by priority (highest first)
    sorted_goals = sorted(goals_list, key=lambda g: -g.priority)

    for goal in sorted_goals:
        remaining = max(0, goal.target_amount - goal.amount_saved)
        months_left = max(1, (goal.deadline.year - today.year) * 12 + (goal.deadline.month - today.month))
        monthly_needed = remaining / months_left
        total_monthly_needed += monthly_needed

        goal_breakdown.append({
            'goal_id': goal.id,
            'goal_name': goal.name,
            'priority': goal.priority,
            'priority_weight': f'{goal.priority}/10',
            'remaining': round(remaining, 2),
            'months_left': months_left,
            'monthly_needed': round(monthly_needed, 2)
        })

    surplus = monthly_savings - total_monthly_needed
    is_feasible = surplus >= 0

    if is_feasible:
        reason = f"✅ All goals are achievable! Monthly surplus: ₹{round(surplus, 2):,}"
    else:
        reason = f"❌ Monthly shortfall: ₹{round(abs(surplus), 2):,}. Some goals need adjustment."

    return {
        'feasible': is_feasible,
        'surplus': round(surplus, 2),
        'surplus_abs': round(abs(surplus), 2),
        'monthly_savings': round(monthly_savings, 2),
        'total_weighted_requirement': round(total_monthly_needed, 2),
        'reason': reason,
        'goal_breakdown': goal_breakdown
    }
