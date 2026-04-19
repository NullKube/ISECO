# ai_engine/speed.py
"""
SPEED TO GOAL MODULE
Calculates estimated time to reach a goal with the current savings rate.
"""

def speed_to_goal(goal, user=None):
    """
    Returns number of months to reach the goal at current savings rate.
    """
    from ai_engine.forecast import get_monthly_averages
    ma = get_monthly_averages(user=user, months=3)
    monthly_savings = ma["monthly_savings"]
    remaining = max(0.0, goal.target_amount - goal.amount_saved)
    if monthly_savings <= 0:
        return float('inf')  # Never, if not saving!
    months = remaining / monthly_savings
    return round(months, 1)
