from django.shortcuts import get_object_or_404, redirect
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
import json
# USER MODELS
from .models import User
from .serializers import UserSerializer
from ai_engine.forecast import forecast_savings_ml, get_monthly_averages
# REQUIRED FOR DASHBOARD
from expenses.models import Expense
from goals.models import Goal
from groups.models import Group
from django.db.models import Sum
from ai_engine.suggestions import generate_suggestions

#AI MODELS
from ai_engine.forecast import forecast_savings, get_monthly_averages
from ai_engine.feasibility import goal_feasibility
from ai_engine.optimizer import prioritize_and_allocate
from ai_engine.speed import speed_to_goal
from ai_engine.suggestions import generate_suggestions
from ai_engine.overspending import detect_overspending
from ai_engine.insights import generate_insights
from ai_engine.strategy import generate_monthly_strategy
from ai_engine.clustering import cluster_spending
from ai_engine.engine import master_ai_output

#second 

from ai_engine.forecast import forecast_savings_ml, get_monthly_averages
from ai_engine.overspending import detect_overspending
from ai_engine.insights import generate_insights
from ai_engine.strategy import generate_monthly_strategy
from ai_engine.clustering import cluster_spending_ml
from ai_engine.feasibility import goal_feasibility
from ai_engine.speed import speed_to_goal
from ai_engine.optimizer import prioritize_and_allocate
from ai_engine.engine import master_ai_output
from ai_engine.suggestions import generate_smart_suggestions

from functools import wraps
from django.http import HttpResponseRedirect

def login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return HttpResponseRedirect('/users/login/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ---------- REGISTER PAGE ----------
class UserRegisterHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "register.html"

    def get(self, request):
        return Response()

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required."}, template_name="register.html")

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, template_name="register.html")

        user = User.objects.create(username=username, password=password)
        request.session['user_id'] = user.id
        request.session['username'] = user.username

        return redirect('/users/dashboard/')


# ---------- USER LIST PAGE ----------
class UserListHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "user_list.html"

    def get(self, request):
        users = User.objects.all()
        return Response({"users": users})


# ---------- USER DETAIL PAGE ----------
class UserDetailHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "user_detail.html"

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response({"user": user})


# ---------- DASHBOARD PAGE ----------


# AI modules



  # Add this at the top of your file if not already there

# ─────────────────────────────────────────────────────────────
# REPLACE your DashboardHTML class in users/views.py with this.
# Everything else in the file stays the same.
# ─────────────────────────────────────────────────────────────

class DashboardHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "dashboard.html"

    def get(self, request):
        if 'user_id' not in request.session:
            return redirect('/users/login/')
        
        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)

        # ── AI TOGGLE ─────────────────────────────────────────
        # Reads from session. Defaults to True (AI on).
        # Flipped by POST /users/toggle-ai/
        ai_enabled = request.session.get("ai_enabled", True)
        # ──────────────────────────────────────────────────────

        # Basic data — always loaded regardless of AI toggle
        try:
            recent_expenses = list(
                Expense.objects.filter(user=user).order_by('-date')[:5].values(
                    'category', 'type', 'date', 'amount'
                )
            )
            active_goals = Goal.objects.filter(user=user, status__in=['active', 'pending'])[:5]
            total_exp = Expense.objects.filter(user=user, type="expense").aggregate(Sum("amount"))["amount__sum"] or 0
            total_inc = Expense.objects.filter(user=user, type="income").aggregate(Sum("amount"))["amount__sum"] or 0
            balance = total_inc - total_exp
            groups = Group.objects.all()[:5]
        except Exception as e:
            print(f"Error loading basic data: {e}")
            recent_expenses, active_goals = [], []
            total_exp = total_inc = balance = 0
            groups = []

        # Forecast — always loaded (it's chart data, not Ollama)
        try:
            forecast_data = forecast_savings_ml(months_ahead=6, user=user)
        except Exception as e:
            print(f"Forecast error: {e}")
            forecast_data = {"method": "error", "forecast": [], "historical_breakdown": [], "current_month": None}

        # Monthly averages — always loaded (pure DB aggregation, no LLM)
        try:
            monthly_avg = get_monthly_averages(months=3, user=user)
        except Exception as e:
            print(f"Monthly avg error: {e}")
            monthly_avg = {"monthly_income": 0, "monthly_expense": 0, "monthly_savings": 0}

        # ── AI-GATED SECTIONS ─────────────────────────────────
        # When ai_enabled=False, all Ollama calls are skipped.
        # Rule-based data (detect_overspending alerts list) still
        # loads — only the LLM explanation text is skipped.
        # ──────────────────────────────────────────────────────

        # Overspending — rule-based detection always runs, LLM explanation gated
        try:
            overspending_raw = detect_overspending(
                user=user,
                include_ai_explanation=ai_enabled  # skip Ollama when AI off
            )
            overspending_list = overspending_raw.get("alerts", [])
            overspending = [a for a in overspending_list if a.get("type") != "success"]
            alerts = overspending_list
        except Exception as e:
            print(f"Overspending error: {e}")
            overspending = []
            alerts = []

        # Suggestions — fully gated (pure LLM output)
        if ai_enabled:
            try:
                suggestions = generate_smart_suggestions(user=user)
            except Exception as e:
                print(f"Suggestions error: {e}")
                suggestions = []
        else:
            suggestions = ["AI is currently disabled. Enable it to see personalized suggestions."]

        # Insights — fully gated
        if ai_enabled:
            try:
                insights_raw = generate_insights(user=user)
                if isinstance(insights_raw, dict):
                    insights = insights_raw.get("insights", insights_raw.get("insight_lines", []))
                else:
                    insights = insights_raw
            except Exception as e:
                print(f"Insights error: {e}")
                insights = []
        else:
            insights = ["AI is currently disabled. Enable it to see behavioral insights."]

        # Strategy — fully gated
        if ai_enabled:
            try:
                strategy_raw = generate_monthly_strategy(user=user)
                if isinstance(strategy_raw, dict):
                    strategy = strategy_raw.get("strategy_lines", [])
                else:
                    strategy = strategy_raw
            except Exception as e:
                print(f"Strategy error: {e}")
                strategy = []
        else:
            strategy = ["AI is currently disabled. Enable it to see your monthly strategy."]

        # Goal Feasibility — rule-based math, not LLM, always runs
        try:
            feasibilities = []
            for g in active_goals:
                result = goal_feasibility(g, user=user)
                feasibilities.append({
                    "goal_id": g.id,
                    "possible": result.get("feasible", result.get("possible", False)),
                    "reason": result.get("reason", ""),
                })
        except Exception as e:
            print(f"Feasibility error: {e}")
            feasibilities = []

        # Speed + Allocation — always runs (math, no LLM)
        try:
            speed_results = {g.id: speed_to_goal(g) for g in active_goals}
        except Exception as e:
            print(f"Speed error: {e}")
            speed_results = {}

        try:
            allocation = prioritize_and_allocate(
                active_goals,
                monthly_avg.get("monthly_savings", 0)
            )
        except Exception as e:
            print(f"Allocation error: {e}")
            allocation = []

        # Clustering — ML math, not LLM, always runs
        try:
            clusters_raw = cluster_spending_ml(user=user)
            method = clusters_raw.get("method", "")
            raw_clusters = clusters_raw.get("clusters", {})
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
        except Exception as e:
            print(f"Clustering error: {e}")
            clusters = {"type": "buckets", "High": [], "Medium": [], "Low": []}

        # Combined AI output — fully gated
        if ai_enabled:
            try:
                combined_results = master_ai_output(user=user)
                combined_result = combined_results.get("combined_output", "Keep tracking your expenses!")
            except Exception as e:
                print(f"Combined AI error: {e}")
                combined_result = "Keep tracking your expenses!"
        else:
            combined_result = "AI is currently disabled. Toggle AI on to see your personalised action plan."

        return Response({
            # Basic
            "recent_expenses": recent_expenses,
            "active_goals": active_goals,
            "total_expense": total_exp,
            "total_income": total_inc,
            "balance": balance,
            "groups": groups,
            "username": user.username,
            "current_user": user,

            # Chart data
            "forecast": json.dumps(forecast_data),
            "monthly_avg": monthly_avg,
            "total_savings": balance,

            # AI sections (some always present, some gated)
            "overspending": overspending,
            "alerts": alerts,
            "suggestions": suggestions,
            "insights": insights,
            "strategy": strategy,
            "feasibilities": feasibilities,
            "clusters": clusters,
            "combined_result": combined_result,

            # Extra
            "speed_results": speed_results,
            "allocation": allocation,

            # Toggle state — passed to template to render button correctly
            "ai_enabled": ai_enabled,
        })  #changed

class ToggleAIView(APIView):
    def post(self, request):
        current = request.session.get("ai_enabled", True)
        request.session["ai_enabled"] = not current
        request.session.modified = True
        return redirect("/users/dashboard/")


# ---------- LOGIN PAGE ----------
class LoginHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "login.html"

    def get(self, request):
        return Response()

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        try:
            user = User.objects.get(username=username, password=password)
            request.session['user_id'] = user.id
            request.session['username'] = user.username
            return redirect("/users/dashboard/")
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, template_name="login.html")


# ---------- LOGOUT ----------
def logout_view(request):
    request.session.flush()
    return redirect("/users/login/")