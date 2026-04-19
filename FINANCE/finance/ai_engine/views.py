# ai_engine/views.py
"""
AI ENGINE VIEWS
Separated into API (JSON) and HTML (template) views.

All views support content negotiation:
- API views return JSON for programmatic access
- HTML views render templates for browser display
- Both use the same underlying logic functions
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum
from datetime import datetime

from expenses.models import Expense
from goals.models import Goal
from users.models import User

from ai_engine.forecast import forecast_savings_ml, get_monthly_averages
from ai_engine.feasibility import goal_feasibility, multi_goal_feasibility
from ai_engine.optimizer import prioritize_and_allocate
from ai_engine.suggestions import generate_suggestions
from ai_engine.overspending import detect_overspending
from ai_engine.insights import generate_insights
from ai_engine.strategy import generate_monthly_strategy
from ai_engine.clustering import cluster_spending_ml
from ai_engine.engine import master_ai_output

# =============================================================================
# UTILITY MIXIN FOR CONTENT NEGOTIATION
# =============================================================================

def get_user_from_request(request):
    """Safely get user from request using Django auth or session user ID."""
    if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
        return request.user

    user_id = request.session.get('user_id')
    if user_id:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    return None


def check_json_requested(request):
    """Check if JSON response was requested via query param or Accept header"""
    if request.GET.get('format') == 'json':
        return True
    accept = request.META.get('HTTP_ACCEPT', '')
    if 'application/json' in accept and 'text/html' not in accept:
        return True
    return False


# =============================================================================
# OVERSPENDING VIEWS
# =============================================================================

def overspending_api(request):
    """API endpoint for overspending detection - returns JSON"""
    user = get_user_from_request(request)
    result = detect_overspending(user=user)
    return JsonResponse(result)


def overspending_html(request):
    """HTML view for overspending report"""
    from ai_engine.clustering import cluster_spending_ml

    user = get_user_from_request(request)
    overspending_result = detect_overspending(user=user)
    clusters_result = cluster_spending_ml(user=user)

    # Process clusters like dashboard does
    method = clusters_result.get("method", "")
    raw_clusters = clusters_result.get("clusters", {})
    if method == "simple_bucketing":
        clusters = {
            "type": "buckets",
            "High": raw_clusters.get("High", []),
            "Medium": raw_clusters.get("Medium", []),
            "Low": raw_clusters.get("Low", []),
        }
    else:
        centers = {}
        for cluster_name, cluster_data in raw_clusters.items():
            label = cluster_data.get("type", cluster_name)
            insight = cluster_data.get("insight", "")
            count = cluster_data.get("count", 0)
            avg = cluster_data.get("avg_amount", 0)
            centers[cluster_name] = f"{label} — {count} transactions, avg ₹{avg:,.0f} ({insight})"
        clusters = {"type": "kmeans", "centers": centers}

    context = {
        'alerts': overspending_result.get('alerts', []),
        'ai_explanation': overspending_result.get('ai_explanation', ''),
        'clusters': clusters,
        'page_title': 'Overspending Alerts',
    }
    return render(request, 'ai/overspending.html', context)


# =============================================================================
# ALERTS VIEWS
# =============================================================================

def alerts_api(request):
    """API endpoint for alerts - returns JSON"""
    user = get_user_from_request(request)
    alerts = detect_overspending(user=user)
    return JsonResponse({'alerts': alerts})


def alerts_html(request):
    """HTML view for all alerts"""
    user = get_user_from_request(request)
    result = detect_overspending(user=user)

    context = {
        'alerts': result.get('alerts', []),
        'ai_explanation': result.get('ai_explanation', ''),
        'page_title': 'All Alerts',
    }
    return render(request, 'ai/alerts.html', context)


# =============================================================================
# SUGGESTIONS VIEWS
# =============================================================================

def suggestions_api(request):
    """API endpoint for suggestions - returns JSON"""
    user = get_user_from_request(request)
    data = generate_suggestions(user=user)
    return JsonResponse(data)


def suggestions_html(request):
    """HTML view for suggestions"""
    user = get_user_from_request(request)
    data = generate_suggestions(user=user)

    context = {
        'suggestions': data.get('suggestions', []),
        'ai_explanation': data.get('ai_explanation', ''),
        'page_title': 'Smart Suggestions',
    }
    return render(request, 'ai/suggestions.html', context)


# =============================================================================
# CLUSTERING VIEWS
# =============================================================================

def clustering_api(request):
    """API endpoint for spending clustering - returns JSON"""
    user = get_user_from_request(request)
    clusters = cluster_spending_ml(user=user)
    return JsonResponse(clusters)


def clustering_html(request):
    """HTML view for spending clustering analysis"""
    user = get_user_from_request(request)
    clusters = cluster_spending_ml(user=user)
    method = clusters.get('method', 'unknown')
    raw_clusters = clusters.get('clusters', {})

    if method == 'simple_bucketing':
        prepared_clusters = {}
        for bucket_name, expenses in raw_clusters.items():
            expenses = expenses or []
            count = len(expenses)
            total_amount = sum((expense.get('amount', 0) for expense in expenses))
            avg_amount = total_amount / count if count else 0
            prepared_clusters[bucket_name] = {
                'expenses': expenses,
                'count': count,
                'total_amount': total_amount,
                'avg_amount': avg_amount,
            }
        raw_clusters = prepared_clusters

    context = {
        'method': method,
        'clusters': raw_clusters,
        'page_title': 'Spending Clusters',
    }
    return render(request, 'ai/clustering.html', context)


# =============================================================================
# STRATEGY VIEWS
# =============================================================================

def strategy_api(request):
    """API endpoint for monthly strategy - returns JSON"""
    user = get_user_from_request(request)
    strategy = generate_monthly_strategy(user=user)
    return JsonResponse(strategy)


def strategy_html(request):
    """HTML view for monthly strategy"""
    user = get_user_from_request(request)
    strategy = generate_monthly_strategy(user=user)

    context = {
        'strategy_lines': strategy.get('strategy_lines', []),
        'ai_explanation': strategy.get('ai_explanation', ''),
        'page_title': 'Monthly Strategy',
    }
    return render(request, 'ai/strategy.html', context)


# =============================================================================
# FORECAST VIEWS
# =============================================================================

def forecast_api(request):
    """API endpoint for savings forecast - returns JSON"""
    user = get_user_from_request(request)
    months = int(request.GET.get('months', 6))
    data = forecast_savings_ml(months_ahead=months, user=user)
    return JsonResponse(data)


def forecast_html(request):
    """HTML view for forecast analysis"""
    user = get_user_from_request(request)
    months = int(request.GET.get('months', 6))
    data = forecast_savings_ml(months_ahead=months, user=user)

    context = {
        'forecast': data.get('forecast', []),
        'historical_breakdown': data.get('historical_breakdown', []),
        'current_month': data.get('current_month', {}),
        'method': data.get('method', 'unknown'),
        'trend_message': data.get('trend_message', ''),
        'model_accuracy': data.get('model_accuracy', ''),
        'accuracy_interpretation': data.get('accuracy_interpretation', ''),
        'ai_explanation': data.get('ai_explanation', ''),
        'summary': data.get('summary', {}),
        'months': months,
        'page_title': 'Savings Forecast',
    }
    return render(request, 'ai/forecast.html', context)


# =============================================================================
# INSIGHTS VIEWS
# =============================================================================

def insights_api(request):
    """API endpoint for behavioral insights - returns JSON"""
    user = get_user_from_request(request)
    insights = generate_insights(user=user)
    return JsonResponse({'insights': insights})


def insights_html(request):
    """HTML view for insights"""
    user = get_user_from_request(request)
    insights = generate_insights(user=user)

    context = {
        'insights': insights,
        'page_title': 'Behavioral Insights',
    }
    return render(request, 'ai/insights.html', context)


# =============================================================================
# FEASIBILITY VIEWS (SINGLE & MULTI)
# =============================================================================

def feasibility_api(request, pk):
    """API endpoint for single goal feasibility - returns JSON"""
    user = get_user_from_request(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    goal = get_object_or_404(Goal, pk=pk, user=user)
    result = goal_feasibility(goal, user=user)
    return JsonResponse(result)


def feasibility_html(request, pk):
    """HTML view for single goal feasibility"""
    user = get_user_from_request(request)
    if not user:
        return redirect('/users/login/')

    goal = get_object_or_404(Goal, pk=pk, user=user)
    result = goal_feasibility(goal, user=goal.user)

    context = {
        'goal': goal,
        'feasibility': result,
        'page_title': f'Feasibility: {goal.name}',
    }
    return render(request, 'ai/feasibility.html', context)


def feasibility_multi_api(request):
    """API endpoint for multi-goal feasibility - returns JSON"""
    user = get_user_from_request(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    goals = Goal.objects.filter(status='active', user=user)
    result = multi_goal_feasibility(goals, user=user)
    return JsonResponse(result)


def feasibility_multi_html(request):
    """HTML view for multi-goal feasibility"""
    user = get_user_from_request(request)
    if not user:
        return redirect('/users/login/')

    goals = Goal.objects.filter(status='active').filter(user=user)

    # Get completed goals for display
    completed_goals = Goal.objects.filter(status='completed')
    if user:
        completed_goals = completed_goals.filter(user=user)
    completed_goals = completed_goals.order_by('-created_at')[:10]  # Limit to 10 most recent

    result = multi_goal_feasibility(goals, user=user)
    monthly_savings = result.get('monthly_savings', 0)

    # Build detailed context for each goal
    goals_with_feasibility = []
    for goal in goals:
        feas = goal_feasibility(goal, user=user)
        progress = 0
        if goal.target_amount and goal.target_amount > 0:
            progress = int((goal.amount_saved / goal.target_amount) * 100)
        
        suggested_deadline = None
        if not feas.get('possible', False) and monthly_savings > 0:
            remaining = max(0, goal.target_amount - goal.amount_saved)
            months_needed = remaining / monthly_savings
            from datetime import timedelta
            today = datetime.now().date()
            suggested_deadline = today + timedelta(days=int(months_needed * 30))
        
        goals_with_feasibility.append({
            'goal': goal,
            'feasibility': feas,
            'progress': progress,
            'suggested_deadline': suggested_deadline,
        })

    context = {
        'goals': goals,
        'goals_with_feasibility': goals_with_feasibility,
        'completed_goals': completed_goals,
        'multi_goal': result,
        'feasible': result.get('feasible', False),
        'monthly_savings': result.get('monthly_savings', 0),
        'total_weighted_requirement': result.get('total_weighted_requirement', 0),
        'surplus': result.get('surplus', 0),
        'surplus_abs': abs(result.get('surplus', 0)),
        'reason': result.get('reason', ''),
        'goal_breakdown': result.get('goal_breakdown', []),
        'page_title': 'Multi-Goal Feasibility',
    }
    return render(request, 'ai/feasibility_multi.html', context)


def feasibility_expired_html(request):
    """HTML view for expired goals feasibility"""
    user = get_user_from_request(request)
    if not user:
        return redirect('/users/login/')

    from datetime import datetime
    today = datetime.now().date()
    
    expired_goals = Goal.objects.filter(deadline__lt=today, status__in=['active', 'pending'])
    if user:
        expired_goals = expired_goals.filter(user=user)

    result = multi_goal_feasibility(expired_goals, user=user)
    monthly_savings = result.get('monthly_savings', 0)

    # Build detailed context for each goal
    goals_with_feasibility = []
    for goal in expired_goals:
        feas = goal_feasibility(goal, user=user)
        progress = 0
        if goal.target_amount and goal.target_amount > 0:
            progress = int((goal.amount_saved / goal.target_amount) * 100)

        suggested_deadline = None
        if not feas.get('possible', False) and monthly_savings > 0:
            remaining = max(0, goal.target_amount - goal.amount_saved)
            months_needed = remaining / monthly_savings
            from datetime import timedelta
            today = datetime.now().date()
            suggested_deadline = today + timedelta(days=int(months_needed * 30))

        goals_with_feasibility.append({
            'goal': goal,
            'feasibility': feas,
            'progress': progress,
            'suggested_deadline': suggested_deadline,
        })

    context = {
        'goals': expired_goals,
        'goals_with_feasibility': goals_with_feasibility,
        'multi_goal': result,
        'feasible': result.get('feasible', False),
        'monthly_savings': result.get('monthly_savings', 0),
        'total_weighted_requirement': result.get('total_weighted_requirement', 0),
        'surplus': result.get('surplus', 0),
        'surplus_abs': abs(result.get('surplus', 0)),
        'reason': result.get('reason', ''),
        'goal_breakdown': result.get('goal_breakdown', []),
        'page_title': 'Expired Goals Feasibility',
    }
    return render(request, 'ai/feasibility_multi.html', context)


# =============================================================================
# MONTHLY AVERAGES VIEWS
# =============================================================================

def monthly_averages_api(request):
    """API endpoint for monthly averages - returns JSON"""
    user = get_user_from_request(request)
    months = int(request.GET.get('months', 3))
    data = get_monthly_averages(user=user, months=months)
    return JsonResponse(data)


def monthly_html(request):
    """HTML view for monthly averages detailed analysis"""
    user = get_user_from_request(request)
    months = int(request.GET.get('months', 3))
    data = get_monthly_averages(user=user, months=months)

    # Get additional context for detailed analysis
    forecast_data = forecast_savings_ml(months_ahead=6, user=user)

    context = {
        'monthly_income': data.get('monthly_income', 0),
        'monthly_expense': data.get('monthly_expense', 0),
        'monthly_savings': data.get('monthly_savings', 0),
        'months_analyzed': data.get('months_analyzed', 0),
        'forecast': forecast_data.get('forecast', []),
        'historical_breakdown': forecast_data.get('historical_breakdown', []),
        'current_month': forecast_data.get('current_month', {}),
        'page_title': 'Monthly Analysis',
    }
    return render(request, 'ai/monthly.html', context)


# =============================================================================
# AI ENGINE (MASTER) VIEWS
# =============================================================================

def ai_engine_api(request):
    """API endpoint for master AI engine - returns JSON"""
    user = get_user_from_request(request)
    result = master_ai_output(user=user)
    return JsonResponse(result)


def ai_engine_html(request):
    """HTML view for the full AI engine dashboard"""
    user = get_user_from_request(request)
    result = master_ai_output(user=user)

    forecast = result.get('forecast', {}) or {}
    monthly_avg = result.get('monthly_avg', {}) or {}
    multi_goal = result.get('multi_goal_feasibility', {}) or {}
    overspending_alerts = result.get('overspending_alerts', {}) or {}
    suggestions = result.get('suggestions', {}) or {}
    insights = result.get('insights', []) or []
    strategy = result.get('strategy', {}) or {}
    clusters = result.get('clusters', {}) or {}

    suggestion_list = []
    if isinstance(suggestions, dict):
        suggestion_list = suggestions.get('suggestions', []) or []
    elif isinstance(suggestions, list):
        suggestion_list = suggestions

    cluster_items = clusters.get('clusters', {}) if isinstance(clusters, dict) else clusters
    cluster_count = len(cluster_items) if hasattr(cluster_items, '__len__') else 0
    cluster_method = clusters.get('method', 'unknown') if isinstance(clusters, dict) else 'unknown'

    forecast_summary = "No forecast data available"
    if forecast.get('current_month'):
        current = forecast.get('current_month', {})
        forecast_summary = f"Current month savings ₹{current.get('savings_mtd', 0)}"
        if current.get('projected_month_end') is not None:
            forecast_summary += f", projected ₹{current.get('projected_month_end', 0)}"
    elif forecast.get('forecast'):
        first = forecast.get('forecast', [{}])[0]
        if first:
            forecast_summary = f"Next month {first.get('month_name', 'N/A')} forecast ₹{first.get('predicted_monthly_savings', 0)}"

    monthly_summary = "No monthly data available"
    if monthly_avg:
        monthly_summary = (
            f"Income ₹{monthly_avg.get('monthly_income', 0)} • "
            f"Expense ₹{monthly_avg.get('monthly_expense', 0)} • "
            f"Savings ₹{monthly_avg.get('monthly_savings', 0)}"
        )

    goal_count = len(result.get('goal_analysis', []) or [])
    goals_summary = "No active goals found"
    if goal_count:
        status_text = "All goals look good" if multi_goal.get('feasible') else "Some goals need attention"
        goals_summary = f"{goal_count} active goals · {status_text}"

    alerts_count = len(overspending_alerts.get('alerts', []) or [])
    alerts_summary = overspending_alerts.get('alerts', [])[0] if alerts_count else "No overspending alerts"

    suggestions_summary = suggestion_list[:2]
    insights_summary = insights[:2]
    strategy_summary = strategy.get('ai_explanation', '') or 'No strategy available yet'
    cluster_summary = f"{cluster_method.title()} clustering found {cluster_count} groups" if cluster_count else 'No cluster analysis available'

    context = {
        'forecast': forecast,
        'monthly_avg': monthly_avg,
        'multi_goal_feasibility': multi_goal,
        'goal_analysis': result.get('goal_analysis', []),
        'allocations': result.get('allocations', {}),
        'overspending_alerts': overspending_alerts,
        'suggestions': suggestions,
        'suggestion_list': suggestion_list,
        'insights': insights,
        'strategy': strategy,
        'clusters': clusters,
        'forecast_summary': forecast_summary,
        'monthly_summary': monthly_summary,
        'goals_summary': goals_summary,
        'alerts_count': alerts_count,
        'alerts_summary': alerts_summary,
        'suggestions_summary': suggestions_summary,
        'insights_summary': insights_summary,
        'strategy_summary': strategy_summary,
        'cluster_summary': cluster_summary,
        'status': result.get('status', ''),
        'page_title': 'AI Overview',
        'page_heading': 'AI Overview',
        'page_subtitle': 'A single place to see forecast, goals, alerts, and strategy at a glance.',
    }
    return render(request, 'ai/engine.html', context)
