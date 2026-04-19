from datetime import datetime, timedelta
from django.db.models import Sum
from goals.models import Goal
from expenses.models import Expense
from ai_engine.feasibility import multi_goal_feasibility
from ai_engine.forecast import get_monthly_averages

# === OLLAMA STRATEGY EXPLAINER ===
import logging
import requests
import time
from requests.exceptions import Timeout, RequestException

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"  # same as forecast
OLLAMA_MODEL = "llama3.2"                      # same model you used
OLLAMA_TIMEOUT = 129 * 60                      # 129 minutes


def explain_monthly_strategy_llm(strategy_lines, user_name="User"):
    """
    Use local LLM (Ollama) to generate a friendly explanation/summary
    of the monthly strategy (list of lines).
    """
    try:
        strategy_text = "\n".join(strategy_lines)

        system_prompt = (
            "You are a friendly Indian financial advisor.\n"
            "You will receive a monthly financial strategy for a user.\n"
            "Explain it in simple English, focusing on practical steps.\n"
            "VERY IMPORTANT RULES:\n"
            "- Use ONLY the rupee amounts, goals, priorities and dates from the text I give you.\n"
            "- Do NOT invent or change any numbers, goals, or deadlines.\n"
            "- Do NOT recommend specific financial products; focus on budgeting, habits and savings.\n"
        )

        user_prompt = (
            f"User name: {user_name}.\n\n"
            "Here is their monthly strategy text:\n\n"
            f"{strategy_text}\n\n"
            "Write a short explanation that:\n"
            "1) Summarizes their income, expenses, and savings for the month.\n"
            "2) Highlights which goals and priorities they should focus on this month.\n"
            "3) Explains how to use the weekly checklist in 2–3 sentences.\n"
            "4) Gives 3–5 simple, actionable tips based on this strategy (without changing any amounts).\n"
            "Rules:\n"
            "- Use ONLY amounts and dates mentioned in the strategy text.\n"
            "- Do NOT add new goals or change priorities.\n"
            "- Keep the explanation under 250 words, easy to understand.\n"
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
            f"Ollama (strategy) response status: {resp.status_code}, "
            f"time: {duration:.2f}s (timeout={OLLAMA_TIMEOUT}s)"
        )
        resp.raise_for_status()
        data = resp.json()

        # Non-streaming /api/chat returns a dict with "message": {"content": "..."}
        if isinstance(data, dict) and "message" in data:
            return data["message"].get("content", "").strip()

        # Fallback if for some reason it's a list of chunks
        if isinstance(data, list):
            parts = []
            for item in data:
                msg = item.get("message", {}).get("content", "")
                if msg:
                    parts.append(msg)
            return "".join(parts).strip()

        return "Could not generate AI explanation for this month's strategy."

    except Timeout as e:
        logger.error(f"Ollama (strategy) request timed out after {OLLAMA_TIMEOUT} seconds: {e}")
        return "AI explanation for this month's strategy is temporarily unavailable due to a timeout."
    except RequestException as e:
        logger.error(f"Ollama (strategy) request failed: {type(e).__name__}: {e}")
        return "AI explanation for this month's strategy is temporarily unavailable. Please try again later."
    except Exception as e:
        logger.error(f"LLM strategy explanation failed: {type(e).__name__}: {e}")
        return "AI explanation for this month's strategy is temporarily unavailable. Please try again later."


def generate_monthly_strategy(user=None):
    """
    Creates a DETAILED monthly action plan:
    - Which goals to focus on THIS month
    - Exact amounts to save weekly/monthly
    - Which expenses to cut
    - Progress milestones

    Returns:
        {
            "strategy_lines": [...],
            "ai_explanation": "..."
        }
    """
    strategy = []

    # Get active goals (both 'active' and 'pending' status)
    goals = Goal.objects.filter(status__in=['active', 'pending'])
    if user:
        goals = goals.filter(user=user)

    if not goals.exists():
        # Keep shape consistent: still provide ai_explanation
        base_lines = ["Nothing to plan. Create a goal to get monthly strategies!"]
        ai_expl = explain_monthly_strategy_llm(
            base_lines,
            user_name=getattr(user, "first_name", "User") or "User",
        )
        return {
            "strategy_lines": base_lines,
            "ai_explanation": ai_expl,
        }

    # Get financial data
    ma = get_monthly_averages(user=user, months=3)
    monthly_savings = ma["monthly_savings"]
    monthly_income = ma["monthly_income"]
    monthly_expense = ma["monthly_expense"]

    # Get feasibility
    feas = multi_goal_feasibility(goals, user)

    # === HEADER ===
    today = datetime.now()
    strategy.append(f"📅 **MONTHLY STRATEGY - {today.strftime('%B %Y')}**")
    strategy.append("")
    strategy.append(f"💰 Your financial snapshot:")
    strategy.append(f"  • Monthly income: ₹{monthly_income:,.2f}")
    strategy.append(f"  • Monthly expenses: ₹{monthly_expense:,.2f}")
    strategy.append(f"  • Monthly savings: ₹{monthly_savings:,.2f}")
    strategy.append("")
    strategy.append("─" * 60)
    strategy.append("")

    # === PRIORITY-BASED STRATEGY ===
    if feas["feasible"]:
        # CAN ACHIEVE ALL GOALS
        surplus = feas["surplus"]
        strategy.append("✅ **GOOD NEWS:** All goals are achievable!")
        strategy.append("")
        strategy.append("🎯 **THIS MONTH'S FOCUS:**")
        strategy.append("")

        # Group goals by priority
        priority_groups = {}
        for goal in goals.order_by('-priority'):
            if goal.priority not in priority_groups:
                priority_groups[goal.priority] = []
            priority_groups[goal.priority].append(goal)

        # Generate week-by-week plan
        week = 1
        for priority in sorted(priority_groups.keys(), reverse=True):
            goals_at_priority = priority_groups[priority]

            strategy.append(f"**Priority {priority} Goals** (Weeks {week}-{week+1}):")
            for goal in goals_at_priority:
                remaining = goal.target_amount - goal.amount_saved
                months_left = max(
                    1,
                    (goal.deadline.year - today.year) * 12
                    + (goal.deadline.month - today.month),
                )
                monthly_need = remaining / months_left
                weekly_need = monthly_need / 4

                strategy.append(f"  • **{goal.name}**")
                strategy.append(f"    Save: ₹{monthly_need:,.2f}/month (₹{weekly_need:,.2f}/week)")
                strategy.append(
                    "    Target this month: Save "
                    f"₹{monthly_need:,.2f} by {(today + timedelta(days=30)).strftime('%b %d')}"
                )

            strategy.append("")
            week += 2

        # Surplus allocation
        if surplus > 1000:
            strategy.append("💡 **Bonus: Surplus allocation**")
            strategy.append(f"  • Extra ₹{surplus:,.2f}/month available!")
            strategy.append(f"  • Week 4: Invest ₹{surplus * 0.5:,.2f} in emergency fund")
            strategy.append(f"  • End of month: Put ₹{surplus * 0.5:,.2f} in index funds/FDs")
            strategy.append("")

    else:
        # CANNOT ACHIEVE ALL GOALS
        shortfall = abs(feas["surplus"])
        strategy.append("⚠️ **BUDGET ALERT:** Cannot achieve all goals with current savings")
        strategy.append(f"  • Shortfall: ₹{shortfall:,.2f}/month")
        strategy.append("")
        strategy.append("🎯 **THIS MONTH'S STRATEGY: Priority Triage**")
        strategy.append("")

        # Identify achievable vs not achievable
        high_priority_goals = goals.filter(priority__gte=7).order_by('-priority')

        if high_priority_goals.exists():
            high_feas = multi_goal_feasibility(high_priority_goals, user)

            if high_feas["feasible"]:
                strategy.append("✅ **Focus on high-priority goals ONLY this month:**")
                strategy.append("")

                week = 1
                for goal in high_priority_goals:
                    remaining = goal.target_amount - goal.amount_saved
                    months_left = max(
                        1,
                        (goal.deadline.year - today.year) * 12
                        + (goal.deadline.month - today.month),
                    )
                    monthly_need = remaining / months_left

                    strategy.append(
                        f"**Week {week}-{week+1}: {goal.name}** (Priority {goal.priority})"
                    )
                    strategy.append(f"  • Save ₹{monthly_need:,.2f} this month")
                    strategy.append("  • Action: Set up auto-transfer on payday")
                    strategy.append("")
                    week += 2

                # What to do about low-priority goals
                low_priority = goals.filter(priority__lt=7)
                if low_priority.exists():
                    strategy.append("⏸️ **Low-priority goals - PAUSE this month:**")
                    for goal in low_priority:
                        new_deadline = goal.deadline + timedelta(days=90)
                        strategy.append(
                            f"  • {goal.name} → Extend deadline to {new_deadline.strftime('%b %Y')}"
                        )
                    strategy.append("")

            else:
                # EVEN HIGH PRIORITY NOT ACHIEVABLE
                strategy.append("🚨 **CRITICAL: Emergency expense cuts needed**")
                strategy.append("")
                strategy.append("**Week 1-2: Immediate actions**")
                strategy.append(f"  1. Cut expenses by ₹{shortfall:,.2f}/month")
                strategy.append(f"  2. OR increase income by ₹{shortfall:,.2f}/month")
                strategy.append("")

                # Show where to cut
                cut_plan = _generate_cutting_plan(user, shortfall)
                strategy.extend(cut_plan)

        else:
            strategy.append(f"**Action required:** Find ₹{shortfall:,.2f}/month")
            strategy.append("")
            cut_plan = _generate_cutting_plan(user, shortfall)
            strategy.extend(cut_plan)

    # === WEEKLY CHECKLIST ===
    strategy.append("")
    strategy.append("─" * 60)
    strategy.append("")
    strategy.append("📋 **WEEKLY CHECKLIST:**")
    strategy.append("")

    # Personalized checklist
    strategy.extend(generate_personalized_weekly_checklist(user))

    # === EXPENSE OPTIMIZATION TIPS ===
    strategy.append("")
    strategy.append("─" * 60)
    strategy.append("")
    strategy.append("💡 **THIS MONTH'S OPTIMIZATION TIPS:**")
    strategy.append("")

    tips = _generate_category_tips(user)
    strategy.extend(tips)

    # === AI EXPLANATION (Ollama) ===
    ai_explanation = explain_monthly_strategy_llm(
        strategy,
        user_name=getattr(user, "first_name", "User") or "User",
    )

    return {
        "strategy_lines": strategy,
        "ai_explanation": ai_explanation,
    }


def generate_personalized_weekly_checklist(user):
    """Generate weekly checklist dynamically based on user expense categories."""
    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)
    cats = qs.values("category").annotate(total=Sum("amount")).order_by("-total")[:5]
    top_cats = [cat['category'].lower() for cat in cats]

    checklist = []
    checklist.append("**Week 1 (Day 1-7):**")
    checklist.append("  ☑ Review last month's expenses")
    checklist.append("  ☑ Set up auto-savings for highest priority goal")

    # Only show "Cancel unused subscription" if subscriptions/entertainment in top 5
    if any(cat in top_cats for cat in ["subscription", "subscriptions", "entertainment", "streaming"]):
        checklist.append("  ☑ Cancel 1 unused subscription")

    # Only show "Meal prep" if food/groceries in top 5
    week2_needed = False
    if any(cat in top_cats for cat in ["food", "dining", "restaurant", "groceries"]):
        week2_needed = True

    checklist.append("")
    checklist.append("**Week 2 (Day 8-14):**")
    checklist.append("  ☑ Track daily expenses")
    if week2_needed:
        checklist.append("  ☑ Meal prep for next 2 weeks (save ₹2000)")
    checklist.append("  ☑ Transfer savings to goal accounts")

    checklist.append("")
    checklist.append("**Week 3 (Day 15-21):**")
    checklist.append("  ☑ Mid-month budget check")
    checklist.append("  ☑ Adjust spending if over budget")
    # Show "carpool" if transport is a top expense
    if any(cat in top_cats for cat in ["transport", "fuel", "uber", "ola"]):
        checklist.append("  ☑ Try carpooling/public transport to save on travel")
    checklist.append("  ☑ Look for extra income opportunities")

    checklist.append("")
    checklist.append("**Week 4 (Day 22-30):**")
    checklist.append("  ☑ Final savings push for monthly goals")
    checklist.append("  ☑ Review progress on all goals")
    checklist.append("  ☑ Plan next month's strategy")
    return checklist


def _generate_cutting_plan(user, amount_needed):
    """Generate specific plan to cut expenses"""
    plan = []

    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)

    cats = qs.values("category").annotate(total=Sum("amount")).order_by("-total")[:5]

    if not cats:
        plan.append("  • Review all expenses and identify cuts")
        return plan

    plan.append(f"**Where to cut ₹{amount_needed:,.2f}/month:**")
    plan.append("")

    cumulative = 0
    for cat in cats:
        cat_name = cat['category']
        cat_total = cat['total']
        cut_amount = cat_total * 0.25  # 25% cut

        if cumulative < amount_needed:
            plan.append(f"  • **{cat_name}**: Reduce by ₹{cut_amount:,.2f}/month")
            plan.append(
                f"    Current: ₹{cat_total:,.2f} → Target: ₹{cat_total - cut_amount:,.2f}"
            )
            cumulative += cut_amount

    plan.append("")
    plan.append(f"  ✅ Total cuts: ₹{cumulative:,.2f}/month")

    return plan


def _generate_category_tips(user):
    """Generate tips based on top spending categories"""
    tips = []

    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)

    cats = qs.values("category").annotate(total=Sum("amount")).order_by("-total")[:3]

    if not cats:
        return ["  • Track your expenses daily to identify saving opportunities"]

    for cat in cats:
        cat_name = cat['category'].lower()

        if cat_name in ['food', 'dining', 'restaurant', 'groceries']:
            tips.append("  🍽️ **Food savings:**")
            tips.append("     • Meal prep Sundays (save ₹500/week)")
            tips.append("     • Pack lunch 3x/week (save ₹300/week)")
            tips.append("     • Use grocery list to avoid impulse buys")

        elif cat_name in ['transport', 'fuel', 'uber', 'ola']:
            tips.append("  🚗 **Transport savings:**")
            tips.append("     • Carpool 2-3 days/week (save ₹400/week)")
            tips.append("     • Use public transport when possible")
            tips.append("     • Combine errands into one trip")

        elif cat_name in ['entertainment', 'subscription', 'streaming']:
            tips.append("  📺 **Entertainment savings:**")
            tips.append("     • Audit subscriptions - cancel unused ones")
            tips.append("     • Share accounts with family (Netflix, Spotify)")
            tips.append("     • Use free alternatives (YouTube, library)")

        elif cat_name in ['shopping', 'clothes', 'fashion']:
            tips.append("  🛍️ **Shopping discipline:**")
            tips.append("     • 30-day rule: Wait before buying")
            tips.append("     • Buy during sales only")
            tips.append("     • Unsubscribe from promotional emails")

    if not tips:
        tips.append("  • Review your top expense categories weekly")
        tips.append("  • Set spending limits for each category")
        tips.append("  • Use cash for discretionary spending")

    return tips