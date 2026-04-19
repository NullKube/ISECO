import csv
import io
from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from .models import Expense
from .serializers import ExpenseSerializer
from users.models import User
from users.serializers import UserSerializer




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


# ---------- ADD EXPENSE PAGE ----------
class ExpenseAddHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "add_expense.html"

    def _parse_date(self, raw_date):
        if not raw_date:
            raise ValueError("Date is required")
        raw_date = raw_date.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw_date, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw_date).date()
        except ValueError:
            raise ValueError("Invalid date format")

    def _normalize_type(self, raw_type):
        if not raw_type:
            return "expense"
        raw_type = raw_type.strip().lower()
        if raw_type in ("income", "inc", "in"):
            return "income"
        if raw_type in ("expense", "exp", "out", "debit"):
            return "expense"
        return "expense"

    def _parse_csv_file(self, uploaded_file):
        raw_content = uploaded_file.read()
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(raw_content))
        if not reader.fieldnames:
            raise ValueError("CSV file must include a header row.")

        header_map = {name.strip().lower(): name for name in reader.fieldnames if name}
        required_columns = {"amount", "category", "type", "date"}
        missing = required_columns - set(header_map.keys())
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

        expenses = []
        errors = []
        for row_number, row in enumerate(reader, start=2):
            if not any((cell or "").strip() for cell in row.values()):
                continue
            try:
                amount_raw = (row.get(header_map["amount"], "") or "").strip()
                category_raw = (row.get(header_map["category"], "") or "").strip()
                type_raw = (row.get(header_map["type"], "") or "").strip()
                date_raw = (row.get(header_map["date"], "") or "").strip()

                if not amount_raw or not category_raw or not type_raw or not date_raw:
                    raise ValueError("Required expense fields are missing")

                amount = float(amount_raw.replace(",", ""))
                expense_type = self._normalize_type(type_raw)
                expense_date = self._parse_date(date_raw)

                expenses.append({
                    "amount": amount,
                    "category": category_raw,
                    "type": expense_type,
                    "date": expense_date,
                })
            except Exception as exc:
                errors.append(f"Row {row_number}: {str(exc)}")

        return expenses, errors

    def get(self, request):
        user = get_user_from_request(request)
        if not user:
            from django.shortcuts import redirect
            return redirect('/users/login/')
        return Response()

    def post(self, request):
        user = get_user_from_request(request)
        if not user:
            from django.shortcuts import redirect
            return redirect('/users/login/')

        csv_file = request.FILES.get("csv_file")
        if csv_file:
            try:
                parsed_expenses, parse_errors = self._parse_csv_file(csv_file)
                imported_count = 0
                for expense_data in parsed_expenses:
                    Expense.objects.create(user=user, **expense_data)
                    imported_count += 1

                message = f"Imported {imported_count} transactions from CSV."
                if parse_errors:
                    message += " Some rows were skipped: " + "; ".join(parse_errors)
                return Response({"message": message})
            except ValueError as exc:
                return Response({"message": f"CSV upload failed: {exc}"})

        amount = request.data.get("amount")
        category = request.data.get("category")
        type = request.data.get("type")
        date = request.data.get("date")

        if not amount or not category or not type or not date:
            return Response({"message": "Please provide all fields or upload a valid CSV file."})

        Expense.objects.create(
            user=user,
            amount=amount,
            category=category,
            type=type,
            date=date
        )

        return Response({"message": "Expense added successfully"})


# ---------- LIST ALL EXPENSES ----------
class ExpenseListHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "expense_list.html"

    def get(self, request):
        user = get_user_from_request(request)
        if not user:
            from django.shortcuts import redirect
            return redirect('/users/login/')

        expenses = Expense.objects.filter(user=user).order_by('-date', '-created_at')
        income_total = sum(exp.amount for exp in expenses if exp.type == 'income')
        expense_total = sum(exp.amount for exp in expenses if exp.type == 'expense')
        net_savings = income_total - expense_total

        return Response({
            "expenses": expenses,
            "income_total": income_total,
            "expense_total": expense_total,
            "net_savings": net_savings,
        })


# ---------- EXPENSE DETAIL PAGE ----------
class ExpenseDetailHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "expense_detail.html"

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        return Response({"expense": expense})
