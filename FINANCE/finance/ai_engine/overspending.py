# ai_engine/overspending.py
"""
OVERSPENDING DETECTION MODULE
Detects unusual spikes or over-budget spending in any category,
and explains them using a local LLM (Ollama) with goal awareness.
"""


from expenses.models import Expense
from goals.models import Goal
from django.db.models import Sum
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import requests
from requests.exceptions import Timeout, RequestException
import time


logger = logging.getLogger(__name__)


# ===== LLM INTEGRATION (Ollama local) =====
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT = 120  # seconds


def explain_overspending_llm(alerts, goals_summary=None, user_name="User"):
    """
    Use local LLM (Ollama) to generate a friendly explanation of overspending alerts
    and how they relate to the user's goals.
    """
    try:
        if goals_summary is None:
            goals_summary = []

        context = {
            "user_name": user_name,
            "alerts": alerts,
            "goals": goals_summary,
        }

        system_prompt = (
    "You are an expert Indian personal finance advisor with strong behavioral psychology awareness.\n"
    "Your role is to analyze user spending data and guide them toward better financial decisions.\n\n"

    "CORE OBJECTIVE:\n"
    "- Help the user identify the most important financial risks.\n"
    "- Connect spending behavior to their financial goals.\n"
    "- Provide practical, realistic, and actionable advice.\n\n"

    "THINKING STRATEGY (INTERNAL - DO NOT OUTPUT):\n"
    "1. Identify the most critical issue based on amount, trend, and urgency.\n"
    "2. Check if this issue affects any high-priority goals.\n"
    "3. Rank issues: critical > goal-related > spikes > minor warnings.\n"
    "4. Focus only on high-impact insights; ignore low-value noise.\n\n"

    "COMMUNICATION STYLE:\n"
    "- Use simple, clear Indian English.\n"
    "- Be supportive but slightly corrective when needed.\n"
    "- Avoid sounding robotic, overly formal, or overly casual.\n"
    "- Speak like a smart financial mentor, not a lecturer.\n\n"

    "STRICT DATA RULES (CRITICAL):\n"
    "- Use ONLY the exact numeric values provided in the input.\n"
    "- Do NOT round, estimate, or modify any numbers.\n"
    "- Do NOT invent any rupee amounts, percentages, or examples.\n"
    "- If a value is missing, do NOT assume or create it.\n"
    "- If suggesting savings, speak qualitatively (e.g., 'a fixed amount regularly').\n\n"

    "ADVICE RULES:\n"
    "- Every suggestion MUST directly relate to a specific alert or goal.\n"
    "- Avoid generic advice like 'spend less' or 'save more'.\n"
    "- Suggestions must be realistic and easy to follow.\n"
    "- Focus on behavior change, not financial products.\n\n"

    "OUTPUT CONSTRAINTS:\n"
    "- Keep response under 200 words.\n"
    "- Do NOT mention data that is not present.\n"
    "- If no serious issues exist, briefly praise the user and reinforce good habits.\n"
)

        user_prompt = (
    f"User name: {user_name}\n\n"

    "Below is the user's financial data (Python dict format):\n"
    f"{context}\n\n"

    "TASK:\n"
    "Analyze the data and generate a clear, actionable financial explanation.\n\n"

    "FOLLOW THIS EXACT STRUCTURE:\n\n"

    "1. Key Issue:\n"
    "- Identify the single most important financial concern.\n"
    "- If multiple issues exist, combine the top 1–2 only.\n\n"

    "2. Why This Matters:\n"
    "- Explain the impact in simple terms.\n"
    "- Mention if this affects any goals or future stability.\n\n"

    "3. What To Do Next:\n"
    "- Provide 3–5 specific, practical actions.\n"
    "- Each action must directly connect to an alert or goal.\n"
    "- Focus on high-impact behavior changes.\n\n"

    "PRIORITY RULES:\n"
    "- Focus primarily on:\n"
    "  1) Critical alerts\n"
    "  2) Goal-related issues\n"
    "  3) Large spending spikes\n"
    "- Ignore minor alerts unless they are significant.\n\n"

    "STRICT RULES:\n"
    "- Do NOT modify any numbers.\n"
    "- Do NOT introduce new rupee amounts.\n"
    "- Do NOT mention categories or goals not present.\n"
    "- Do NOT give generic or vague advice.\n\n"

    "TONE:\n"
    "- Supportive, practical, and slightly corrective.\n"
    "- Clear and easy to understand.\n\n"

    "Keep the response concise and under 200 words."
)

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        start = time.time()
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        duration = time.time() - start
        logger.info(
            f"Ollama overspending response status: {resp.status_code}, "
            f"time: {duration:.2f}s (timeout={OLLAMA_TIMEOUT}s)"
        )
        resp.raise_for_status()
        data = resp.json()

        # Non-streaming /api/chat final object has "message" with "content"
        if isinstance(data, dict) and "message" in data:
            return data["message"].get("content", "").strip()

        # Fallback if response is somehow a list of chunks
        if isinstance(data, list):
            parts = []
            for item in data:
                msg = item.get("message", {}).get("content", "")
                if msg:
                    parts.append(msg)
            return "".join(parts).strip()

        return "Could not generate AI explanation."

    except Timeout as e:
        logger.error(f"Ollama overspending request timed out after {OLLAMA_TIMEOUT} seconds: {e}")
        return "AI overspending explanation is temporarily unavailable due to a timeout. Please try again later."
    except RequestException as e:
        logger.error(f"Ollama overspending request failed: {type(e).__name__}: {e}")
        return "AI overspending explanation is temporarily unavailable. Please try again later."
    except Exception as e:
        logger.error(f"Overspending LLM explanation failed: {type(e).__name__}: {e}")
        return "AI overspending explanation is temporarily unavailable. Please try again later."


def _get_current_month_range():
    today = datetime.now().date()
    current_month_start = datetime(today.year, today.month, 1).date()
    if today.month == 12:
        next_month_start = datetime(today.year + 1, 1, 1).date()
    else:
        next_month_start = datetime(today.year, today.month + 1, 1).date()
    return today, current_month_start, next_month_start


def _get_previous_month_range(today):
    if today.month == 1:
        prev_month_start = datetime(today.year - 1, 12, 1).date()
        prev_month_end = datetime(today.year - 1, 12, 31).date()
    else:
        prev_month_start = datetime(today.year, today.month - 1, 1).date()
        prev_month_end = datetime(today.year, today.month, 1).date() - timedelta(days=1)
    return prev_month_start, prev_month_end


def _build_goals_summary(user, current_month_total):
    """
    Build a compact summary of active goals and how current spending/saving
    relates to them. This is primarily for the LLM and optional UI display.
    """
    # Safe for AnonymousUser
    if not user or not getattr(user, "is_authenticated", False):
        return []

    today = datetime.now().date()
    _, current_month_start, _ = _get_current_month_range()

    goals = Goal.objects.filter(user=user, status="active")
    summary = []

    for g in goals:
        summary.append({
            "name": g.name,
            "target_amount": g.target_amount,
            "amount_saved": g.amount_saved,
            "remaining": max(g.target_amount - g.amount_saved, 0),
            "deadline": g.deadline.isoformat(),
            "priority": g.priority,
            "status": g.status,
        })

    return summary


def detect_overspending(user=None, include_ai_explanation=True, user_name="User"):
    """
    Returns a dict with:
      - alerts: list of alert dictionaries with overspending details.
      - ai_explanation: optional LLM-generated explanation string.

    Alert format:
      {"category": "Food", "amount_over": 500, "period": "This month", "type": "warning", ...}
    """

    qs = Expense.objects.filter(type="expense")
    # Safe filter: only apply user filter if authenticated
    if user is not None and getattr(user, "is_authenticated", False):
        qs = qs.filter(user=user)

    alerts = []

    # Get current month data
    today, current_month_start, _ = _get_current_month_range()

    current_month_qs = qs.filter(date__gte=current_month_start)
    current_month_total = current_month_qs.aggregate(Sum("amount"))["amount__sum"] or 0

    # Alert 1: Total monthly spending threshold
    if current_month_total > 60000:
        alerts.append({
            "category": "Overall Spending",
            "amount_over": current_month_total - 60000,
            "period": "This month",
            "type": "critical",
            "message": f"Total monthly expenses crossed ₹60,000 (Currently: ₹{current_month_total:,.2f})",
        })

    # Alert 2: Category-wise overspending (>25% of total)
    category_totals = current_month_qs.values("category").annotate(total=Sum("amount"))

    for cat in category_totals:
        category_name = cat["category"] or "Uncategorized"
        category_total = cat["total"] or 0

        if current_month_total > 0:
            percentage = (category_total / current_month_total) * 100

            if percentage > 25:
                alerts.append({
                    "category": category_name,
                    "amount_over": category_total - (0.25 * current_month_total),
                    "period": "This month",
                    "type": "warning",
                    "percentage": round(percentage, 1),
                    "message": f"{category_name}: {percentage:.1f}% of spending (Should be <25%)",
                })

    # Alert 3: Compare with previous month (spike detection)
    prev_month_start, prev_month_end = _get_previous_month_range(today)

    prev_month_qs = qs.filter(date__gte=prev_month_start, date__lte=prev_month_end)
    prev_month_total = prev_month_qs.aggregate(Sum("amount"))["amount__sum"] or 0

    if prev_month_total > 0 and current_month_total > prev_month_total * 1.3:  # 30% increase
        increase = current_month_total - prev_month_total
        alerts.append({
            "category": "Monthly Trend",
            "amount_over": increase,
            "period": "Month-over-month",
            "type": "alert",
            "message": (
                f"Spending increased by ₹{increase:,.2f} compared to last month "
                f"({((increase / prev_month_total) * 100):.1f}% increase)"
            ),
        })

    # Alert 4: Category-wise spike (50% increase from last month)
    prev_category_totals = prev_month_qs.values("category").annotate(total=Sum("amount"))
    prev_cat_dict = {cat["category"]: cat["total"] for cat in prev_category_totals}

    for cat in category_totals:
        category_name = cat["category"] or "Uncategorized"
        current_total = cat["total"] or 0
        prev_total = prev_cat_dict.get(cat["category"], 0)

        if prev_total > 0 and current_total > prev_total * 1.5:  # 50% increase
            increase = current_total - prev_total
            alerts.append({
                "category": category_name,
                "amount_over": increase,
                "period": "vs Last month",
                "type": "spike",
                "message": (
                    f"{category_name} spending spiked by ₹{increase:,.2f} "
                    f"({((increase / prev_total) * 100):.1f}% increase)"
                ),
            })

    # ===== Goal-aware alerts (using Goal model) =====
    goals_summary = _build_goals_summary(user, current_month_total)

    for g in goals_summary:
        deadline = datetime.fromisoformat(g["deadline"]).date()
        days_left = (deadline - today).days
        if days_left > 0:
            progress_pct = (g["amount_saved"] / g["target_amount"]) * 100 if g["target_amount"] > 0 else 0
            if g["priority"] <= 3 and progress_pct < 50 and days_left < 90:
                alerts.append({
                    "category": "Goal Progress",
                    "goal_name": g["name"],
                    "amount_over": 0,
                    "period": "Until deadline",
                    "type": "goal_warning",
                    "message": (
                        f"High priority goal '{g['name']}' is only {progress_pct:.1f}% complete "
                        f"with {days_left} days left (Remaining: ₹{g['remaining']:,.2f})."
                    ),
                })

    # If no alerts, add a positive message
    if not alerts:
        alerts.append({
            "category": "All Good",
            "amount_over": 0,
            "period": "Current",
            "type": "success",
            "message": "No overspending detected! Keep up the great work! 🎉",
        })

    result = {
        "alerts": alerts,
        "ai_explanation": None,
    }

    if include_ai_explanation:
        result["ai_explanation"] = explain_overspending_llm(
            alerts=alerts,
            goals_summary=goals_summary,
            user_name=user_name or "User",
        )

    return result
