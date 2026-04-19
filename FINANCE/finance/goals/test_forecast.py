"""
Test script to validate goal forecast calculations
Run: python manage.py shell < test_forecast.py
"""

from goals.models import Goal
from goals.feasibility_engine import check_goal_feasibility, calculate_monthly_savings
from datetime import datetime, timedelta
from django.contrib.auth.models import User

# Get the first user with goals
user = User.objects.first()

if not user:
    print("No users found!")
else:
    print(f"\n{'='*60}")
    print(f"Testing Forecast for User: {user.username}")
    print(f"{'='*60}\n")
    
    # Get their actual monthly savings
    actual_savings = calculate_monthly_savings(user)
    print(f"✓ Calculated Monthly Savings: ₹{actual_savings:,.2f}")
    
    # Get their active goals
    goals = Goal.objects.filter(user=user, status='active')
    
    if not goals.exists():
        print("✗ No active goals found!")
    else:
        print(f"\n📊 Testing {goals.count()} goal(s):\n")
        
        for goal in goals:
            print(f"Goal: {goal.name}")
            print(f"  Target Amount: ₹{goal.target_amount:,.0f}")
            print(f"  Amount Saved: ₹{goal.amount_saved:,.0f}")
            print(f"  Deadline: {goal.deadline.strftime('%B %d, %Y')}")
            
            # Calculate forecast
            today = datetime.now().date()
            remaining_days = (goal.deadline - today).days
            remaining_months = remaining_days / 30.0
            
            print(f"  Days Remaining: {remaining_days}")
            print(f"  Months Remaining: {remaining_months:.2f}")
            
            # Get feasibility analysis
            feasibility = check_goal_feasibility(goal, user=user)
            
            # Calculate projected balance
            projected_at_deadline = goal.amount_saved + (actual_savings * remaining_months)
            required_monthly = goal.target_amount / remaining_months if remaining_months > 0 else float('inf')
            
            print(f"\n  💰 Current Balance: ₹{goal.amount_saved:,.0f}")
            print(f"  📈 Projected at Deadline: ₹{projected_at_deadline:,.0f}")
            print(f"  📊 Monthly Savings Needed: ₹{required_monthly:,.0f}")
            print(f"  💵 Your Monthly Savings: ₹{actual_savings:,.0f}")
            print(f"  ✓ Feasible: {feasibility['is_feasible']}")
            
            if not feasibility['is_feasible']:
                print(f"  ⚠️  Shortfall: ₹{feasibility['shortfall']:,.0f}/month")
                print(f"  💡 Reason: {feasibility['reason']}")
            
            print(f"\n{'-'*60}\n")

print("✅ Forecast validation complete!")
