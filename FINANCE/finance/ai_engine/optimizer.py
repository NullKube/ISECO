"""
GOAL PRIORITIZATION & ALLOCATION
ENHANCED: Full priority-weighted, deadline-/feasibility-aware allocation with detailed recommendations.
"""

from datetime import datetime

def prioritize_and_allocate(goals, monthly_savings):
    """
    Priority-weighted allocation of savings across goals.
    Includes detailed feasibility checks, recommendations, and actionable feedback for each goal.
    """
    goals = list(goals)
    # Only consider goals that are active/pending and need more saving
    goals = [
        g for g in goals
        if getattr(g, "status", "active") in ['active', 'pending']
        and float(getattr(g, "target_amount", 0)) - float(getattr(g, "amount_saved", 0)) > 0
    ]

    if not goals or monthly_savings <= 0:
        # Optionally, return a message explaining why
        return [{
            "status": "No allocation: No actionable goals or no savings available this month."
        }]

    total_weight = sum(max(1, int(getattr(g, "priority", 1))) for g in goals)
    today = datetime.now().date()
    allocations = []

    for g in goals:
        weight = max(1, int(getattr(g, "priority", 1)))
        target_amount = float(getattr(g, "target_amount", 0))
        amount_saved = float(getattr(g, "amount_saved", 0))
        remaining = max(0, target_amount - amount_saved)
        deadline = getattr(g, "deadline", None)
        alloc = (weight / total_weight) * monthly_savings

        # Calculate how many months needed at recommended allocation
        months_to_complete = (remaining / alloc) if alloc > 0 else float('inf')
        # Determine months remaining until deadline
        if deadline:
            months_until_deadline = max(0, (deadline.year - today.year)*12 + (deadline.month - today.month))
        else:
            months_until_deadline = None

        on_track = False
        if months_until_deadline is not None and months_until_deadline > 0:
            on_track = months_to_complete <= months_until_deadline

        # Dynamic progress/status message
        if months_until_deadline is None:
            deadline_label = "No deadline"
        elif months_to_complete == float('inf'):
            deadline_label = f"💸 Not achievable at current rate"
        elif on_track:
            deadline_label = f"Finish in {round(months_to_complete,1)} mo. ({months_until_deadline} left)"
        else:
            deadline_label = f"⚠️ Needs {round(months_to_complete,1)} mo., deadline in {months_until_deadline}"

        allocations.append({
            "goal_id": getattr(g, "id", None),
            "goal_name": getattr(g, "name", ""),
            "priority": weight,
            "target_amount": target_amount,
            "amount_saved": amount_saved,
            "remaining": round(remaining, 2),
            "recommended_monthly_allocation": round(alloc, 2),
            "months_to_complete_at_rate": round(months_to_complete, 1) if months_to_complete != float('inf') else "N/A",
            "months_until_deadline": months_until_deadline if months_until_deadline is not None else "N/A",
            "on_track": on_track,
            "status": (
                "✅ On track"
                if on_track else (
                    "⚠️ Behind schedule" if months_to_complete != float('inf') else "💸 Not achievable"
                )
            ),
            "progress_comment": deadline_label
        })

    # Sort by priority (highest first)
    allocations.sort(key=lambda x: x["priority"], reverse=True)
    return allocations
