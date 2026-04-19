"""
Split Analyzer - AI-powered expense split suggestion engine

Analyzes individual financial situations (savings, goals, spending patterns)
and suggests fair expense splits based on each member's capacity to pay.
"""

from datetime import datetime
from django.db.models import Q, Sum
from expenses.models import Expense
from goals.models import Goal
from ai_engine.feasibility import goal_feasibility


def get_user_financial_summary(user):
    """
    Fetch comprehensive financial data for a user.

    Returns:
        dict with: total_income, total_expenses, current_savings,
                   active_goals, monthly_savings, financial_health
    """
    # Get all expenses for the user
    expenses_qs = Expense.objects.filter(user=user)

    total_income = float(
        expenses_qs.filter(type='income').aggregate(total=Sum('amount'))['total'] or 0.0
    )
    total_expenses = float(
        expenses_qs.filter(type='expense').aggregate(total=Sum('amount'))['total'] or 0.0
    )
    current_savings = total_income - total_expenses

    # Calculate monthly average
    dates = list(expenses_qs.values_list('date', flat=True))
    unique_months = len(set((d.year, d.month) for d in dates)) if dates else 1
    divisor = max(unique_months, 1)
    monthly_savings = current_savings / divisor

    # Get active goals
    active_goals = Goal.objects.filter(user=user, status='active')
    high_priority_goals = active_goals.filter(priority__gte=7)

    # Determine financial health
    if current_savings < 0:
        health_score = 0.2  # In debt
        health_label = "In Debt"
    elif current_savings < 5000:
        health_score = 0.4  # Low savings
        health_label = "Low Savings"
    elif current_savings < 25000:
        health_score = 0.6  # Moderate savings
        health_label = "Moderate Savings"
    elif current_savings < 100000:
        health_score = 0.8  # Good savings
        health_label = "Good Savings"
    else:
        health_score = 1.0  # Excellent savings
        health_label = "Excellent Savings"

    return {
        'user_id': user.id,
        'username': user.username,
        'total_income': round(total_income, 2),
        'total_expenses': round(total_expenses, 2),
        'current_savings': round(current_savings, 2),
        'monthly_savings': round(monthly_savings, 2),
        'active_goals_count': active_goals.count(),
        'high_priority_goals_count': high_priority_goals.count(),
        'health_score': health_score,
        'health_label': health_label,
    }


def calculate_capacity_score(financial_summary):
    """
    Calculate how much each user can afford to pay (0-1 scale).

    Factors in:
    - Current savings (base capacity)
    - High-priority active goals (reduces capacity)

    Returns:
        float: capacity score (0 to 1)
    """
    # Base capacity from savings health
    capacity = financial_summary['health_score']

    # Reduce capacity if user has high-priority goals
    if financial_summary['high_priority_goals_count'] > 0:
        # Each high-priority goal reduces capacity by 0.15 (max reduction: 1 goal = -0.15)
        goal_reduction = min(financial_summary['high_priority_goals_count'] * 0.15, 0.3)
        capacity = max(0.1, capacity - goal_reduction)  # Floor at 0.1 (minimum capacity)

    return round(capacity, 2)


def suggest_split(group, expense):
    """
    Generate AI-powered split suggestions for an expense.

    Analyzes: financial history, savings, active goals, spending patterns
    Suggests splits proportional to each member's financial capacity

    Returns:
        dict with: splits (list), total, analysis_data, rationale
    """
    from groups.models import GroupMember

    # Fetch all group members
    members = group.members.all()

    if not members.exists():
        return {
            'success': False,
            'message': 'Group has no members',
            'splits': []
        }

    expense_amount = expense.amount
    num_members = members.count()

    # Collect financial data and capacity scores
    financial_data = {}
    capacity_scores = {}
    total_capacity = 0

    for member in members:
        user = member.user
        financial_summary = get_user_financial_summary(user)
        capacity_score = calculate_capacity_score(financial_summary)

        financial_data[user.id] = financial_summary
        capacity_scores[user.id] = capacity_score
        total_capacity += capacity_score

    # Handle edge case: if all capacity scores are very low
    if total_capacity == 0:
        total_capacity = num_members
        for user_id in capacity_scores:
            capacity_scores[user_id] = 1.0

    # Generate suggested splits
    splits = []
    for member in members:
        user = member.user
        user_capacity = capacity_scores[user.id]

        # Calculate suggested amount proportional to capacity
        suggested_amount = (user_capacity / total_capacity) * expense_amount
        suggested_amount = round(suggested_amount, 2)

        # Generate rationale
        financial_summary = financial_data[user.id]
        rationale = generate_rationale(financial_summary, user_capacity)

        splits.append({
            'user_id': user.id,
            'username': user.username,
            'suggested_amount': suggested_amount,
            'adjusted_amount': None,
            'final_amount': suggested_amount,
            'rationale': rationale,
            'financial_summary': financial_summary,
            'capacity_score': user_capacity,
        })

    # Prepare analysis data for storage
    analysis_data = {
        'expense_id': expense.id,
        'group_id': group.id,
        'expense_amount': expense_amount,
        'num_members': num_members,
        'total_capacity': round(total_capacity, 2),
        'financial_data': financial_data,
        'capacity_scores': capacity_scores,
        'timestamp': datetime.now().isoformat(),
    }

    return {
        'success': True,
        'expense': {
            'id': expense.id,
            'group_id': group.id,
            'amount': expense_amount,
            'description': expense.description,
        },
        'splits': splits,
        'total': round(expense_amount, 2),
        'analysis_data': analysis_data,
        'algorithm_version': 'v1',
    }


def generate_rationale(financial_summary, capacity_score):
    """
    Generate human-readable explanation for why this split amount was suggested.
    """
    savings = financial_summary['current_savings']
    goals = financial_summary['active_goals_count']
    high_priority_goals = financial_summary['high_priority_goals_count']

    if savings < 0:
        reason = f"Currently in debt (₹{abs(savings):,.0f}). Suggested minimal amount to help recovery."
    elif savings < 5000:
        reason = f"Low savings (₹{savings:,.0f}). Reduced share to preserve emergency funds."
    elif savings > 100000:
        reason = f"Strong savings (₹{savings:,.0f}). Can afford higher share."
    else:
        reason = f"Moderate savings (₹{savings:,.0f})."

    if high_priority_goals > 0:
        reason += f" {high_priority_goals} high-priority goal(s) active – share adjusted accordingly."

    reason += f" Capacity: {int(capacity_score * 100)}%"

    return reason


def auto_rebalance_split(expense, adjusted_split):
    """
    When one user adjusts their split amount, rebalance others proportionally.

    Args:
        expense: GroupExpense object
        adjusted_split: dict with {user_id: adjusted_amount}

    Returns:
        dict with rebalanced amounts for all members
    """
    from groups.models import GroupMember

    group = expense.group
    members = group.members.all()

    # Find the user who adjusted their amount
    adjusted_user_id = list(adjusted_split.keys())[0]
    adjusted_amount = adjusted_split[adjusted_user_id]

    # Calculate remaining amount
    remaining = expense.amount - adjusted_amount

    if remaining < 0:
        return {
            'success': False,
            'message': f'Adjusted amount exceeds total expense (₹{expense.amount})',
            'rebalanced': {}
        }

    # Fetch current capacity scores
    financial_data = {}
    capacity_scores = {}
    total_capacity = 0

    for member in members:
        if member.user_id == adjusted_user_id:
            continue  # Skip the adjusted user

        user = member.user
        financial_summary = get_user_financial_summary(user)
        capacity_score = calculate_capacity_score(financial_summary)

        financial_data[user.id] = financial_summary
        capacity_scores[user.id] = capacity_score
        total_capacity += capacity_score

    # Default to equal split if no other capacity
    if total_capacity == 0:
        num_other_members = members.count() - 1
        if num_other_members > 0:
            total_capacity = num_other_members
            for user_id in capacity_scores:
                capacity_scores[user_id] = 1.0

    # Rebalance remaining members
    rebalanced = {adjusted_user_id: adjusted_amount}

    for member in members:
        if member.user_id == adjusted_user_id:
            continue

        user_capacity = capacity_scores.get(member.user_id, 1.0)
        rebalanced_amount = (user_capacity / total_capacity) * remaining
        rebalanced[member.user_id] = round(rebalanced_amount, 2)

    # Verify total
    total_check = sum(rebalanced.values())

    return {
        'success': True,
        'rebalanced': rebalanced,
        'total': round(total_check, 2),
        'matches_expense': abs(total_check - expense.amount) < 0.01,
    }
