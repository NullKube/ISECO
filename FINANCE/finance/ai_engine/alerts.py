from datetime import datetime, timedelta
from expenses.models import Expense
from django.db.models import Sum

def generate_alerts(user=None):
    alerts = []

    now = datetime.now().date()
    # 1. 3-day overspend: if sum(last 3 days) > 1.5x normal 3-day spend
    last_3 = now - timedelta(days=3)
    qs = Expense.objects.filter(date__gte=last_3)
    if user:
        qs = qs.filter(user=user)
    spent_3 = qs.aggregate(total=Sum("amount"))["total"] or 0.0

    # compute average daily over last 60 days
    past_period = now - timedelta(days=60)
    qs2 = Expense.objects.filter(date__gte=past_period)
    if user:
        qs2 = qs2.filter(user=user)
    total_60 = qs2.aggregate(total=Sum("amount"))["total"] or 0.0
    avg_daily = (total_60 / 60) if total_60 else 0.0

    if avg_daily > 0 and spent_3 > avg_daily * 3 * 1.5:  # 50% spike threshold
        alerts.append({
            "type": "overspend",
            "message": f"Spending spike detected: ₹{spent_3:,.0f} spent in last 3 days (avg daily ₹{avg_daily:,.0f}).",
            "severity": "high"
        })

    # 2. Category overspend alert for top category in last 30 days
    last_30 = Expense.objects.filter(date__gte=now - timedelta(days=30))
    if user:
        last_30 = last_30.filter(user=user)
    total_30 = last_30.aggregate(total=Sum("amount"))["total"] or 0.0
    top_cat = last_30.values("category").annotate(total=Sum("amount")).order_by("-total").first()
    if top_cat and total_30:
        pct = (top_cat["total"] / total_30) * 100
        # Suggest limit if top category > 20%
        if pct > 20:
            alerts.append({
                "type": "category_overspend",
                "message": f"Overspending in '{top_cat['category']}' detected ({pct:.1f}% of this month's spend). Try limiting to 20% of total spending.",
                "severity": "medium"
            })

    return alerts
