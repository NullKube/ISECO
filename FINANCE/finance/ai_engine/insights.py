"""
BEHAVIORAL INSIGHTS MODULE
Analyses spending and saving patterns for actionable insights.
"""

from expenses.models import Expense

def generate_insights(user=None):
    """
    Returns up to 4-5 qualitative/quantitative spending insights for dashboard.
    """
    from django.db.models import Sum
    from datetime import datetime, timedelta

    insights = []
    qs = Expense.objects.filter(type="expense")
    if user:
        qs = qs.filter(user=user)
    total = qs.aggregate(Sum("amount"))["amount__sum"] or 0
    if total == 0:
        insights.append("No spending data available for insights.")
        return insights

    # 1. Top spending categories (percent & ₹)
    category_totals = list(qs.values("category").annotate(total=Sum("amount")).order_by("-total"))
    if category_totals:
        for i, cat in enumerate(category_totals[:3]):
            pct = (cat["total"] / total) * 100
            insights.append(
                f"Your No.{i+1} spending category is '{cat['category']}' — ₹{cat['total']:,.0f} ({pct:.1f}% of total)."
            )
            # Special tip if > 35% in one area
            if pct > 35:
                insights.append(
                    f"Over 35% of your spending is in '{cat['category']}' — opportunity to cut back."
                )

    # 2. Large individual expense
    month_expenses = list(qs.values_list('amount', flat=True))
    if month_expenses and max(month_expenses) > 0.4 * total:
        insights.append("A single purchase was over 40% of your total spend—plan to spread big expenses across months.")

    # 3. Spend spike vs previous month
    # Compare total spend in last 30 days to previous 30 days
    today = datetime.now().date()
    last_30 = qs.filter(date__gte=today - timedelta(days=30)).aggregate(Sum("amount"))["amount__sum"] or 0
    prev_30 = qs.filter(date__gte=today - timedelta(days=60), date__lt=today - timedelta(days=30)).aggregate(Sum("amount"))["amount__sum"] or 0
    if prev_30 > 0:
        delta = last_30 - prev_30
        pct_change = (delta / prev_30) * 100
        if abs(pct_change) > 15:
            trend_emoji = "📈" if pct_change > 0 else "📉"
            if pct_change > 0:
                insights.append(
                    f"{trend_emoji} Spending increased by {pct_change:.1f}% vs previous month. Check for unusual purchases."
                )
            else:
                insights.append(
                    f"{trend_emoji} Good job! Spending dropped by {abs(pct_change):.1f}% vs previous month."
                )

    # 4. Subscription/recurring category flag
    recurring_cats = ["subscription", "subscriptions", "entertainment", "streaming"]
    for cat in category_totals[:3]:
        if cat["category"].lower() in recurring_cats and cat["total"] > 0.08 * total:
            insights.append(f"You spent ₹{cat['total']:,.0f} on subscriptions/streaming — audit subscriptions for savings.")

    # 5. Grocery or shopping savings tip if high
    for cat in category_totals[:3]:
        if cat["category"].lower() in ["shopping", "groceries", "grocery"] and (cat["total"] > 0.20 * total):
            insights.append(f"Your '{cat['category']}' spending is high. Try meal prep or bulk shopping for savings.")

    # Only show up to 5
    return insights[:5]
