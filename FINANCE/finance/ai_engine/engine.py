# ai_engine/engine.py
"""
MASTER AI ENGINE - Orchestrates all AI modules
FIXES:
- Now returns user-specific data
- Handles errors gracefully
- Caches results to avoid redundant computation
"""

from .forecast import forecast_savings_ml, get_monthly_averages
from .feasibility import goal_feasibility, multi_goal_feasibility
from .optimizer import prioritize_and_allocate
from .suggestions import generate_smart_suggestions
from .overspending import detect_overspending
from .insights import generate_insights
from .strategy import generate_monthly_strategy
from .clustering import cluster_spending_ml

def master_ai_output(user=None):
    """
    Combined AI output with ALL modules.
    FIXED: Now properly handles user filtering and returns goal-aware data.
    """
    try:
        # === FORECASTING ===
        forecast = forecast_savings_ml(months_ahead=6, user=user)
        monthly = get_monthly_averages(user=user, months=3)
        
        # === GOAL ANALYSIS ===
        from goals.models import Goal
        goals = Goal.objects.filter(status='active')
        if user:
            goals = goals.filter(user=user)
        
        # Multi-goal feasibility check
        multi_feas = multi_goal_feasibility(goals, user=user)
        
        # Individual goal analysis
        goal_analysis = []
        for goal in goals[:5]:  # Top 5 goals
            feas = goal_feasibility(goal, user=user)
            goal_analysis.append({
                "goal_id": goal.id,
                "goal_name": goal.name,
                "feasibility": feas
            })
        
        # === OPTIMIZATION ===
        allocations = prioritize_and_allocate(goals, monthly["monthly_savings"])
        
        # === ALERTS & SUGGESTIONS ===
        overs = detect_overspending(user=user)
        sugs = generate_smart_suggestions(user=user)  # FIXED: Now goal-aware
        insights = generate_insights(user=user)
        strategy = generate_monthly_strategy(user=user)
        
        # === CLUSTERING ===
        clusters = cluster_spending_ml(user=user)  # FIXED: Real ML clustering
        
        return {
            "forecast": forecast,
            "monthly_avg": monthly,
            "multi_goal_feasibility": multi_feas,  # NEW
            "goal_analysis": goal_analysis,  # NEW
            "allocations": allocations,  # NEW
            "overspending_alerts": overs,
            "suggestions": sugs,
            "insights": insights,
            "strategy": strategy,
            "clusters": clusters,
            "status": "success"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "forecast": {"forecast": []},
            "suggestions": ["Error generating suggestions. Please check your data."]
        }