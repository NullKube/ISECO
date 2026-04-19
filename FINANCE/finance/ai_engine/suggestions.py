from django.db.models import Sum
from expenses.models import Expense
from datetime import datetime, timedelta
import logging
import requests
from requests.exceptions import Timeout, RequestException
import time

logger = logging.getLogger(__name__)

# ===== LLM INTEGRATION (Ollama local) =====
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT = 180  # seconds


def generate_smart_suggestions(user=None):
    """
    PRIORITY-FOCUSED SUGGESTIONS
    Shows which priorities are achievable and exact savings plan
    """
    from goals.models import Goal
    from goals.feasibility_engine import check_goal_feasibility
    from ai_engine.forecast import get_monthly_averages
    from dateutil.relativedelta import relativedelta

    suggestions = []

    # Get active goals
    goals = Goal.objects.filter(status__in=["active", "pending"])
    if user:
        goals = goals.filter(user=user)

    if not goals.exists():
        suggestions.append("📝 No active goals found. Create goals to get personalized planning advice.")
        suggestions.extend(_general_expense_suggestions(user))
        return suggestions

    # Get financial status
    ma = get_monthly_averages(user=user, months=3)
    monthly_savings = ma.get("monthly_savings", 0)
    
    # Get all other active goals for competing goals analysis
    all_active_goals = list(Goal.objects.filter(status='active', user=user).exclude(pk__in=goals.values_list('pk', flat=True))) if user else []

    # === PRIORITY-BASED FEASIBILITY CHECK ===
    suggestions.append("🎯 **PRIORITY-BASED FEASIBILITY ANALYSIS:**")
    suggestions.append("")

    # Group goals by priority (highest first)
    priority_groups = {}
    for goal in goals:
        if goal.priority not in priority_groups:
            priority_groups[goal.priority] = []
        priority_groups[goal.priority].append(goal)

    # Sort priorities (highest first)
    sorted_priorities = sorted(priority_groups.keys(), reverse=True)

    achievable_priorities = []
    tight_priorities = []
    impossible_priorities = []

    # Check each priority level
    for priority in sorted_priorities:
        goals_at_priority = priority_groups[priority]

        suggestions.append(f"{'─' * 60}")
        suggestions.append(
            f"**PRIORITY {priority}** "
            f"{'(HIGHEST)' if priority == sorted_priorities[0] else '(LOWEST)' if priority == sorted_priorities[-1] else ''}"
        )
        suggestions.append("")

        for goal in goals_at_priority:
            # Fallback for blank goal names
            goal_name = goal.name.strip() if getattr(goal, "name", "") else f"Goal #{goal.id}"

            remaining = goal.target_amount - goal.amount_saved
            progress_pct = round((goal.amount_saved / goal.target_amount) * 100, 1) if goal.target_amount else 0.0

            today = datetime.now().date()
            months_left = max(
                1,
                (goal.deadline.year - today.year) * 12 + (goal.deadline.month - today.month),
            )

            # If done, say so and skip savings analysis for this goal
            if remaining <= 0:
                suggestions.append(f"  • **{goal_name}** - 🎉 Goal Achieved!")
                suggestions.append(
                    f"    Target: ₹{goal.target_amount:,.0f} | Saved: ₹{goal.amount_saved:,.0f} ({progress_pct}%)"
                )
                continue

            # Monthly amount needed for THIS goal
            monthly_need = remaining / months_left

            # Use proper feasibility check from goals.feasibility_engine
            feasibility = check_goal_feasibility(goal, competing_goals=all_active_goals, user=user)
            is_feasible = feasibility['is_feasible']
            monthly_need = feasibility['required_monthly']
            actual_monthly = feasibility['actual_monthly']
            
            # Determine status based on feasibility
            if is_feasible:
                status = "✅ EASILY ACHIEVABLE"
                achievable_priorities.append((priority, goal, monthly_need))
            else:
                # Check if it's borderline/tight (less than 20% over capacity)
                if actual_monthly > 0 and monthly_need / actual_monthly <= 1.2:
                    status = "⚠️ ACHIEVABLE (Tight budget)"
                    tight_priorities.append((priority, goal, monthly_need))
                else:
                    status = "❌ NOT ACHIEVABLE (Insufficient savings)"
                    impossible_priorities.append((priority, goal, monthly_need))

            suggestions.append(f"  • **{goal_name}** - {status}")
            suggestions.append(
                f"    Target: ₹{goal.target_amount:,.0f} | Saved: ₹{goal.amount_saved:,.0f} ({progress_pct}%)"
            )
            suggestions.append(
                f"    Remaining: ₹{remaining:,.0f} | Deadline: {goal.deadline.strftime('%b %Y')} ({months_left} months)"
            )
            suggestions.append(f"    Required: ₹{monthly_need:,.2f}/month")
            suggestions.append(f"    Available: ₹{actual_monthly:,.2f}/month")

            # For not-achievable goals: show completion forecast, options to meet deadline
            if status.startswith("❌") and actual_monthly > 0:
                realistic_months = int((remaining / actual_monthly) + 0.999)  # round up
                realistic_finish_date = today + relativedelta(months=realistic_months)
                suggestions.append(
                    f"    👉 At your current savings rate (₹{actual_monthly:,.2f}/mo), you'll finish in "
                    f"**{realistic_months} months** (~{realistic_finish_date.strftime('%b %Y')})."
                )
                extra_needed = monthly_need - actual_monthly

                # Only mention extra needed if it is positive
                if extra_needed > 0:
                    suggestions.append(
                        f"    💡 To finish by the original deadline, you need to increase savings by "
                        f"₹{extra_needed:,.2f}/month."
                    )
                    suggestions.append(
                        f"    🚀 Options: (a) Increase income by ₹{extra_needed:,.2f}/month | "
                        f"(b) Cut expenses by ₹{extra_needed:,.2f}/month | "
                        f"(c) Extend deadline to {realistic_finish_date.strftime('%b %Y')}"
                    )
                else:
                    # Already saving enough or more; don't suggest negative increase
                    suggestions.append(
                        "    🚀 You are already saving enough monthly for this goal based on the current plan."
                    )

            suggestions.append("")

    suggestions.append(f"{'─' * 60}")
    suggestions.append("")

    # === SUMMARY: What can you afford? ===
    suggestions.append("📊 **FEASIBILITY SUMMARY:**")
    suggestions.append("")
    suggestions.append(f"Your monthly savings: ₹{monthly_savings:,.2f}")
    
    # Calculate total needed from all achievable + tight goals
    total_needed = sum([need for _, _, need in achievable_priorities + tight_priorities])
    suggestions.append(f"Total needed for achievable goals: ₹{total_needed:,.2f}")
    suggestions.append("")

    if not impossible_priorities:
        surplus = monthly_savings - total_needed
        suggestions.append(
            f"✅ **GREAT NEWS!** You can afford all your goals with ₹{surplus:,.2f}/month to spare!"
        )
        suggestions.append("")
        suggestions.append("💡 **Recommended actions:**")
        suggestions.append(f"  1. Set up auto-savings of ₹{total_needed:,.2f}/month")
        suggestions.append(f"  2. Use remaining ₹{surplus:,.2f}/month for emergency fund or investments")
    else:
        impossible_names = [g.name or f"Goal #{g.id}" for _, g, _ in impossible_priorities]
        suggestions.append(
            f"⚠️ **{len(impossible_priorities)} goal(s) need adjustment:** {', '.join(impossible_names)}"
        )
        suggestions.append("")

        # Show what priorities ARE achievable
        if achievable_priorities or tight_priorities:
            suggestions.append("✅ **YOU CAN ACHIEVE:**")
            affordable = achievable_priorities + tight_priorities
            for priority, goal, monthly_need in affordable:
                goal_name = goal.name.strip() if getattr(goal, "name", "") else f"Goal #{goal.id}"
                suggestions.append(f"  • Priority {priority}: {goal_name} (₹{monthly_need:,.2f}/month)")
            suggestions.append("")

        if impossible_priorities:
            suggestions.append("❌ **NEED ADJUSTMENT (with current budget):**")
            for priority, goal, monthly_need in impossible_priorities:
                goal_name = goal.name.strip() if getattr(goal, "name", "") else f"Goal #{goal.id}"
                suggestions.append(f"  • Priority {priority}: {goal_name} (₹{monthly_need:,.2f}/month)")
            suggestions.append("")

    # === ACTION PLAN ===
    suggestions.append(f"{'─' * 60}")
    suggestions.append("")
    suggestions.append("🎯 **YOUR ACTION PLAN:**")
    suggestions.append("")

    if not impossible_priorities:
        # CAN AFFORD ALL - Show savings breakdown
        suggestions.append("**Monthly Savings Breakdown:**")
        for priority in sorted_priorities:
            goals_at_priority = priority_groups[priority]
            total_for_priority = 0
            for g in goals_at_priority:
                feasibility = check_goal_feasibility(g, competing_goals=all_active_goals, user=user)
                total_for_priority += feasibility.get('required_monthly', 0)
            if total_for_priority > 0:
                suggestions.append(f"  • Priority {priority}: ₹{total_for_priority:,.2f}/month")

    else:
        # CANNOT AFFORD ALL
        suggestions.append(
            f"**OPTION 1: Focus on highest priority goals**"
        )
        affordable_need = 0
        affordable_goals = []

        for priority in sorted_priorities:
            goals_at_priority = priority_groups[priority]
            for g in goals_at_priority:
                feasibility = check_goal_feasibility(g, competing_goals=all_active_goals, user=user)
                monthly_need = feasibility.get('required_monthly', 0)

                if affordable_need + monthly_need <= monthly_savings:
                    affordable_need += monthly_need
                    goal_name = g.name.strip() if getattr(g, "name", "") else f"Goal #{g.id}"
                    affordable_goals.append((priority, goal_name, monthly_need))

        if affordable_goals:
            suggestions.append(f"  With ₹{monthly_savings:,.2f}/month, you CAN achieve:")
            for priority, name, need in affordable_goals:
                suggestions.append(f"    • Priority {priority}: {name} (₹{need:,.2f}/month)")

        suggestions.append("")
        shortfall = sum([need for _, _, need in impossible_priorities]) if impossible_priorities else 0
        suggestions.append(
            f"**OPTION 2: Increase income by ₹{shortfall:,.2f}/month**"
        )
        suggestions.append("  • Freelance/side hustle")
        suggestions.append("  • Ask for raise")
        suggestions.append("  • Part-time work")

        suggestions.append("")
        suggestions.append(
            f"**OPTION 3: Cut expenses by ₹{shortfall:,.2f}/month**"
        )

        # Suggest specific cuts
        cut_suggestions = _suggest_category_cuts(user, shortfall)
        suggestions.extend(cut_suggestions)

        suggestions.append("")
        suggestions.append("**OPTION 4: Extend deadlines for lowest priority goals**")
        for priority, goal, monthly_need in impossible_priorities:
            goal_name = goal.name.strip() if getattr(goal, "name", "") else f"Goal #{goal.id}"
            new_deadline = goal.deadline + timedelta(days=90)
            suggestions.append(f"  • {goal_name} → Extend to {new_deadline.strftime('%b %Y')}")

    # Add spending insights
    suggestions.append("")
    suggestions.append(f"{'─' * 60}")
    suggestions.append("")
    suggestions.extend(_general_expense_suggestions(user))

    return suggestions


def _suggest_category_cuts(user, amount_needed):
    """Helper: Suggest which categories to cut to save amount_needed"""
    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)

    cats = qs.values("category").annotate(total=Sum("amount")).order_by("-total")[:5]

    if not cats:
        return ["  • Review all expenses and identify discretionary spending"]

    suggestions = []
    suggestions.append(f"  **Where to cut ₹{amount_needed:,.2f}/month:**")

    cumulative_cut = 0
    for cat in cats:
        cat_name = cat["category"] or "Unnamed category"
        cat_total = cat["total"]

        # Suggest cutting 25% from top categories
        potential_cut = cat_total * 0.25

        if cumulative_cut < amount_needed:
            suggestions.append(
                f"    • Reduce **{cat_name}** by ₹{potential_cut:,.2f}/month "
                f"(25% cut from ₹{cat_total:,.2f})"
            )
            cumulative_cut += potential_cut

    if cumulative_cut >= amount_needed:
        suggestions.append(f"    ✅ Total savings: ₹{cumulative_cut:,.2f}/month (covers shortfall!)")

    return suggestions


def _general_expense_suggestions(user):
    """General expense optimization advice"""
    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)

    total = qs.aggregate(Sum("amount"))["amount__sum"] or 0.0
    suggestions = []

    if total == 0:
        return ["💡 Add expenses to get personalized spending insights"]

    suggestions.append("📊 **SPENDING INSIGHTS:**")
    suggestions.append("")

    # Top 3 spending categories
    cats = qs.values("category").annotate(total=Sum("amount")).order_by("-total")[:3]
    if cats:
        for i, cat in enumerate(cats, 1):
            cat_name = cat["category"] or "Unnamed category"
            cat_total = cat["total"]
            pct = round((cat_total / total) * 100, 1)

            suggestions.append(f"  {i}. **{cat_name}**: ₹{cat_total:,.2f} ({pct}% of total spending)")

            # Category-specific advice (keep soft, no extreme cuts)
            lower = (cat_name or "").lower()
            if lower in ["food", "dining", "restaurant", "groceries"]:
                suggestions.append("     💡 Try meal prep a few times a week to reduce food costs.")
            elif lower in ["entertainment", "subscription", "streaming"]:
                suggestions.append("     💡 Audit subscriptions and cancel rarely used services.")
            elif lower in ["transport", "fuel", "uber", "ola"]:
                suggestions.append(
                    "     💡 Consider combining trips, carpooling, or using public transport sometimes to optimise fuel use."
                )
            elif lower in ["shopping", "clothes", "fashion"]:
                suggestions.append("     💡 Use a 30-day rule before non-essential purchases.")

    return suggestions


def explain_suggestions_llm(suggestions, user_name="User"):
    """
    Use local LLM (Ollama) to rewrite the structured suggestions into a
    human-friendly, realistic explanation without changing any numbers.
    """
    try:
        text_block = "\n".join(suggestions)

        # ✅ SYSTEM PROMPT (clean triple string)
        system_prompt = """You are a highly practical personal finance strategist for Indian users.
You think in constraints, trade-offs, and real-life behavior — not theory.

YOUR ROLE:
- Interpret a pre-computed financial plan.
- Convert it into realistic, actionable guidance.
- Help the user make decisions within their existing lifestyle.

CORE THINKING RULES (INTERNAL):
1. Identify what spending is adjustable vs non-adjustable.
2. Focus on behavior changes, not ideal scenarios.
3. Prefer optimization over elimination.
4. Suggest trade-offs, not sacrifices.
5. Prioritize consistency over intensity.

ANTI-GENERIC FILTER (STRICT):
- Reject any advice that could apply to any user.
- Every suggestion MUST reference actual data.
- If a suggestion can be given without seeing the data, DO NOT include it.

STRICT PROHIBITIONS:
- NO generic advice (e.g., 'reduce expenses', 'save more').
- NO unrealistic suggestions (e.g., 'stop fuel').
- NO unnecessary income advice unless mathematically required.
- NO lifestyle-breaking recommendations.

DATA INTEGRITY RULES:
- NEVER change any rupee values.
- NEVER invent numbers.
- ONLY use values present in the input.

BEHAVIORAL GUIDELINES:
- Suggest small, high-impact adjustments.
- Prefer reducing frequency over stopping completely.
- Suggest substitutions or timing changes.
- Keep actions realistic.

OUTPUT STYLE:
- Clear, direct, practical.
- No fluff, no lectures.
"""

        # ✅ USER PROMPT (clean triple f-string)
        user_prompt = f"""User name: {user_name}

Below is the financial plan:
{text_block}

YOUR TASK:
Convert this into a realistic, behavior-focused action plan.

HOW TO THINK:
- User cannot drastically change lifestyle
- Focus on practical adjustments
- Keep everything realistic

OUTPUT STRUCTURE:

1. Situation Summary (2–3 lines)
- Explain the situation
- Highlight main constraint

2. Practical Adjustments (4–6 points)
- Must reference actual data
- Use:
  • Reduce frequency (not eliminate)
  • Optimize usage
  • Substitute cheaper options
  • Shift timing

3. Trade-off Strategy
- Explain what must be prioritized
- What can be delayed (NOT removed)

STRICT RULES:
- NO generic advice
- NO unrealistic cuts
- NO new numbers
- NO unnecessary income suggestions

QUALITY CHECK:
- If advice is generic → remove it

Keep under 250 words.
"""

       

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
            f"Ollama suggestions response status: {resp.status_code}, "
            f"time: {duration:.2f}s (timeout={OLLAMA_TIMEOUT}s)"
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and "message" in data:
            return data["message"].get("content", "").strip()

        if isinstance(data, list):
            parts = []
            for item in data:
                msg = item.get("message", {}).get("content", "")
                if msg:
                    parts.append(msg)
            return "".join(parts).strip()

        return "AI suggestions are temporarily unavailable."

    except Timeout as e:
        logger.error(f"Ollama suggestions request timed out after {OLLAMA_TIMEOUT} seconds: {e}")
        return "AI suggestions are temporarily unavailable due to a timeout. Please try again later."
    except RequestException as e:
        logger.error(f"Ollama suggestions request failed: {type(e).__name__}: {e}")
        return "AI suggestions are temporarily unavailable. Please try again later."
    except Exception as e:
        logger.error(f"Suggestions LLM explanation failed: {type(e).__name__}: {e}")
        return "AI suggestions are temporarily unavailable. Please try again later."


def generate_suggestions(user=None):
    """
    LEGACY FUNCTION - kept for backward compatibility.
    Returns both the raw smart suggestions and an AI explanation.
    """
    raw = generate_smart_suggestions(user)
    user_name = getattr(user, "username", None) or "User"
    ai_text = explain_suggestions_llm(raw, user_name=user_name)
    return {
        "suggestions": raw,
        "ai_explanation": ai_text,
    }


def generate_goal_suggestions(user=None):
    """
    Returns structured goal data with AI-generated recommendations.
    For each goal, includes:
    - can_mark_completed: True if amount_saved >= target_amount
    - can_extend_deadline: True if status in ['active', 'paused']
    - suggested_deadline: Computed date if not feasible
    - status: "feasible" or "not_feasible"

    This is used by the goal suggestions view to display actionable recommendations.
    """
    from goals.models import Goal
    from ai_engine.feasibility import goal_feasibility
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    # Only include active goals (not completed, missed, or paused)
    goals = Goal.objects.filter(status="active")
    if user:
        goals = goals.filter(user=user)

    results = []
    for goal in goals:
        feasibility = goal_feasibility(goal, user)

        # Calculate suggested deadline if not feasible
        suggested_deadline = None
        if not feasibility["possible"] and feasibility.get("monthly_savings", 0) > 0:
            remaining = goal.target_amount - goal.amount_saved
            monthly_savings = feasibility.get("monthly_savings", 1)
            # Avoid division by zero
            if monthly_savings > 0:
                months_needed = int(remaining / monthly_savings) + 1
                suggested_deadline = datetime.now().date() + relativedelta(months=months_needed)

        # Determine if goal can be marked as completed
        can_mark_completed = goal.amount_saved >= goal.target_amount

        # Determine if deadline can be extended (only active or paused goals)
        can_extend_deadline = goal.status in ["active", "paused"]

        # Determine feasibility status
        status = "feasible" if feasibility["possible"] else "not_feasible"

        results.append({
            "goal_id": goal.id,
            "goal_name": goal.name,
            "can_mark_completed": can_mark_completed,
            "can_extend_deadline": can_extend_deadline,
            "suggested_deadline": suggested_deadline,
            "status": status,
            "target_amount": goal.target_amount,
            "amount_saved": goal.amount_saved,
            "remaining": goal.target_amount - goal.amount_saved,
            "months_left": feasibility.get("months_left", 0),
            "required_per_month": feasibility.get("required_per_month", 0),
            "monthly_savings": feasibility.get("monthly_savings", 0),
            "reason": feasibility.get("reason", ""),
        })

    return results
