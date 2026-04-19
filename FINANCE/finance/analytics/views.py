from datetime import datetime
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from expenses.models import Expense
from goals.models import Goal



class AnalyticsSummaryHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "summary.html"

    def get(self, request):
        total_expense = Expense.objects.filter(type="expense").aggregate(Sum("amount"))["amount__sum"] or 0
        total_income = Expense.objects.filter(type="income").aggregate(Sum("amount"))["amount__sum"] or 0
        active_goals = Goal.objects.filter(status="pending").count()

        return Response({
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "active_goals": active_goals
        })


class AnalyticsMonthlyHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "monthly.html"

    def get(self, request):
        current_month = datetime.now().month
        current_year = datetime.now().year

        monthly_expense = Expense.objects.filter(
            date__year=current_year,
            date__month=current_month,
            type="expense"
        ).aggregate(Sum("amount"))["amount__sum"] or 0

        monthly_income = Expense.objects.filter(
            date__year=current_year,
            date__month=current_month,
            type="income"
        ).aggregate(Sum("amount"))["amount__sum"] or 0

        return Response({
            "month": current_month,
            "year": current_year,
            "monthly_expense": monthly_expense,
            "monthly_income": monthly_income
        })


class AnalyticsCategoryHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "category.html"

    def get(self, request):
        category_data = (
            Expense.objects
            .filter(type="expense")
            .values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        return Response({"categories": category_data})
