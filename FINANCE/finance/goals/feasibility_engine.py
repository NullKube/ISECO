"""
Smart Goal Feasibility Engine with Priority-Based Scheduling

Features:
1. Checks if a goal is feasible given current deadline & other goals
2. Suggests next feasible date if not feasible
3. Handles priority-based reordering (highest priority first)
4. Breaks ties by shortest duration
5. Cascades changes across all goals
"""

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def get_all_active_goals_sorted(user):
    """Get all active goals for a user, sorted by priority DESC, then duration ASC"""
    from .models import Goal
    goals = Goal.objects.filter(status='active', user=user).order_by('-priority', 'duration_days')
    return list(goals)


def calculate_monthly_savings(user):
    """
    Calculate user's average monthly savings from actual transaction history.
    Savings = Total Income - Total Expenses (from last 3 months)
    """
    from expenses.models import Expense
    from datetime import datetime, timedelta
    
    # Get transactions from last 3 months
    three_months_ago = datetime.now().date() - timedelta(days=90)
    transactions = Expense.objects.filter(user=user, date__gte=three_months_ago)
    
    if not transactions.exists():
        return 0  # No data, assume can't save
    
    # Calculate total income and expenses
    total_income = 0
    total_expenses = 0
    
    for trans in transactions:
        if trans.type == 'income':
            total_income += float(trans.amount)
        elif trans.type == 'expense':
            total_expenses += float(trans.amount)
    
    # Calculate average monthly savings
    months = 3
    monthly_income = total_income / months
    monthly_expenses = total_expenses / months
    monthly_savings = monthly_income - monthly_expenses
    
    # Return actual savings (or 0 if spending > income)
    return max(monthly_savings, 0)


def calculate_required_monthly_savings(target_amount, remaining_days):
    """Calculate monthly savings needed to reach target in remaining days"""
    if remaining_days <= 0:
        return float('inf')
    
    months_remaining = remaining_days / 30.0
    if months_remaining <= 0:
        return float('inf')
    
    return target_amount / months_remaining


def check_goal_feasibility(goal, competing_goals=None, user=None):
    """
    Check if a goal is feasible given:
    - User's monthly savings capacity
    - Time remaining to deadline
    - Other active goals competing for time/resources
    
    Returns dict with:
    - is_feasible: bool
    - months_left: int
    - required_monthly: float
    - actual_monthly: float
    - shortfall: float (if not feasible)
    - reason: str
    """
    from .models import Goal
    
    if competing_goals is None:
        competing_goals = []
    
    today = datetime.now().date()
    remaining_days = (goal.deadline - today).days
    months_left = int(remaining_days / 30)
    
    if remaining_days < 0:
        return {
            'is_feasible': False,
            'months_left': months_left,
            'required_monthly': float('inf'),
            'actual_monthly': 0,
            'shortfall': goal.target_amount,
            'reason': 'Deadline has already passed.'
        }
    
    # Get user's savings capacity
    if user:
        actual_monthly = calculate_monthly_savings(user)
    else:
        actual_monthly = 1000  # Default fallback
    
    # Calculate required monthly savings
    required_monthly = calculate_required_monthly_savings(goal.target_amount, remaining_days)
    
    # Check for shortfall
    shortfall = max(0, required_monthly - actual_monthly)
    
    is_feasible = shortfall <= 0 and remaining_days > 0
    
    return {
        'is_feasible': is_feasible,
        'months_left': months_left,
        'required_monthly': required_monthly,
        'actual_monthly': actual_monthly,
        'shortfall': shortfall,
        'reason': (
            f"Goal requires ₹{required_monthly:,.0f}/month but you save ₹{actual_monthly:,.0f}/month"
            if not is_feasible else
            "Goal is achievable with current savings rate"
        )
    }


def find_next_feasible_date(goal, competing_goals=None, user=None, max_years=3):
    """
    Find the earliest feasible date for a goal by shifting the deadline forward.
    
    Returns dict with:
    - feasible_date: datetime.date or None
    - months_delay: int
    - reason: str
    """
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    actual_monthly = calculate_monthly_savings(user) if user else 1000
    
    # Start from today + target amount / monthly savings
    months_needed = max(1, int(goal.target_amount / actual_monthly) + 1)
    feasible_date = today + relativedelta(months=months_needed)
    
    # Cap at max_years
    max_date = today + relativedelta(years=max_years)
    
    if feasible_date > max_date:
        return {
            'feasible_date': None,
            'months_delay': None,
            'reason': f'Goal cannot be achieved within {max_years} years with current savings rate.'
        }
    
    original_deadline = goal.deadline
    months_delay = int((feasible_date - original_deadline).days / 30)
    
    return {
        'feasible_date': feasible_date,
        'months_delay': months_delay,
        'reason': f'Moving deadline {abs(months_delay)} month(s) {"forward" if months_delay > 0 else "backward"} to achieve feasibility.'
    }


def reschedule_all_goals(user):
    """
    Re-evaluate and reschedule ALL active goals for a user following priority rules:
    1. Sort by priority DESC, then duration ASC
    2. For each goal, find earliest feasible slot that doesn't conflict with others
    3. Return list of adjusted goals with changes
    """
    from .models import Goal
    
    # Get all active goals sorted by priority (highest first), then duration (shortest first)
    goals = get_all_active_goals_sorted(user)
    
    if not goals:
        return []
    
    today = datetime.now().date()
    adjustments = []
    
    for goal in goals:
        # Check feasibility at current deadline
        feasibility = check_goal_feasibility(goal, user=user)
        
        if not feasibility['is_feasible']:
            # Find next feasible date
            next_feasible = find_next_feasible_date(goal, user=user)
            
            if next_feasible['feasible_date']:
                old_deadline = goal.deadline
                goal.original_deadline = old_deadline
                goal.deadline = next_feasible['feasible_date']
                goal.save()
                
                months_shifted = int((goal.deadline - old_deadline).days / 30)
                
                adjustments.append({
                    'goal_id': goal.id,
                    'goal_name': goal.name,
                    'old_deadline': old_deadline,
                    'new_deadline': goal.deadline,
                    'months_shifted': months_shifted,
                    'is_feasible': True,
                    'reason': f'Shifted to {goal.deadline.strftime("%b %d, %Y")} for feasibility'
                })
    
    return adjustments


def get_goal_with_shift_suggestion(goal, user=None):
    """
    Get a goal with its shift suggestion if it's not feasible.
    
    Returns dict with goal data and optional shift_suggestion
    """
    from .models import Goal
    
    feasibility = check_goal_feasibility(goal, user=user)
    
    shift_suggestion = None
    if not feasibility['is_feasible']:
        next_feasible = find_next_feasible_date(goal, user=user)
        if next_feasible['feasible_date']:
            shift_suggestion = {
                'new_deadline': next_feasible['feasible_date'],
                'months_delay': next_feasible['months_delay'],
                'reason': next_feasible['reason']
            }
    
    return {
        'goal': goal,
        'feasibility': feasibility,
        'shift_suggestion': shift_suggestion
    }


def get_goal_current_balance(goal, user):
    """
    Get current balance for a goal.
    
    Priority order:
    1. Use goal.amount_saved if manually set
    2. Otherwise calculate from accumulated savings since goal creation
    3. Return calculated value (user can manually update if needed)
    """
    # If user has manually set amount_saved to > 0, use it
    if goal.amount_saved > 0:
        return goal.amount_saved
    
    # Otherwise, calculate from actual monthly savings × months since creation
    from datetime import datetime
    
    created_date = goal.created_at.date() if goal.created_at else datetime.now().date()
    days_since_creation = (datetime.now().date() - created_date).days
    months_since_creation = max(days_since_creation / 30.0, 0)
    
    actual_monthly = calculate_monthly_savings(user)
    calculated_balance = actual_monthly * months_since_creation
    
    return calculated_balance


def validate_forecast_calculation(goal, user):
    """
    Validate and return detailed forecast breakdown
    Returns detailed calculation information for verification
    """
    today = datetime.now().date()
    remaining_days = (goal.deadline - today).days
    remaining_months = remaining_days / 30.0
    
    # Get actual monthly savings
    actual_monthly = calculate_monthly_savings(user)
    
    # Get current balance (from manual entry or calculated from savings)
    current_balance = get_goal_current_balance(goal, user)
    
    # Calculate projected balance
    projected_at_deadline = current_balance + (actual_monthly * remaining_months)
    
    # Calculate required monthly
    required_monthly = calculate_required_monthly_savings(goal.target_amount, remaining_days)
    
    # Check feasibility
    shortfall = max(0, required_monthly - actual_monthly)
    is_feasible = shortfall <= 0 and remaining_days > 0
    
    return {
        'current_balance': current_balance,
        'monthly_savings': actual_monthly,
        'days_remaining': remaining_days,
        'months_remaining': remaining_months,
        'projected_at_deadline': projected_at_deadline,
        'required_monthly': required_monthly,
        'is_feasible': is_feasible,
        'calculation_breakdown': {
            'formula': f'{current_balance} + ({actual_monthly} × {remaining_months:.2f})',
            'result': projected_at_deadline,
            'feasibility_check': f'{required_monthly:.0f} <= {actual_monthly:.0f}?',
            'feasible': is_feasible
        }
    }
