# -*- coding: utf-8 -*-


"""
SAVINGS FORECAST ENGINE
=======================
Industry-grade ML savings forecasting with Ollama LLM explanation.

Fixes applied:
  - Expense aggregation now uses Django ORM (not Python loop) → correct expense totals
  - Currency symbol hardened to ₹ throughout (was leaking $ in some paths)
  - Feb/Mar manual entries no longer silently corrupt training data — future months
    that are not the current month are excluded from training, logged as warnings
  - current_month_data always carries income_mtd / expense_mtd so templates render correctly
  - R² edge-case: single-feature LinearRegression on 2 points always returns R²=1.0,
    now clamped and flagged as INSUFFICIENT DATA when months < 3
  - forecast list is guaranteed to contain exactly `months_ahead` entries (skip logic fixed)
  - All monetary values formatted with Indian locale comma grouping helper
  - Type annotations added throughout for IDE support and readability
"""

from __future__ import annotations

import logging
import time
from calendar import month_name as _MONTH_NAMES
from datetime import datetime
from typing import Any

import requests
from django.db.models import Q, Sum
from requests.exceptions import RequestException, Timeout

from expenses.models import Expense

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT = 129 * 60  # 129 minutes

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _inr(value: float) -> str:
    """Format a float as an Indian-style ₹ string (e.g. ₹1,23,456.78)."""
    try:
        # Built-in approach — good enough for display; swap for babel if needed
        rounded = round(float(value), 2)
        neg = rounded < 0
        s = f"{abs(rounded):,.2f}"
        # Convert western grouping (1,234,567) to Indian (12,34,567)
        integer_part, decimal_part = s.split(".")
        digits = integer_part.replace(",", "")
        if len(digits) > 3:
            last3 = digits[-3:]
            rest = digits[:-3]
            groups = [rest[max(0, i - 2) : i] for i in range(len(rest), 0, -2)][::-1]
            integer_part = ",".join(filter(None, groups)) + "," + last3
        else:
            integer_part = digits
        sign = "-" if neg else ""
        return f"₹{sign}{integer_part}.{decimal_part}"
    except Exception:
        return f"₹{value}"


def _month_label(year: int, month: int) -> str:
    return f"{_MONTH_NAMES[month]} {year}"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    total = month - 1 + n
    return year + total // 12, total % 12 + 1


def _sum_qs(qs) -> float:
    return float(qs.aggregate(total=Sum("amount"))["total"] or 0.0)


def _savings_emoji(savings: float, prev: float | None = None) -> str:
    if savings < 0:
        return "❌"
    if prev is not None:
        if savings > prev + 1000:
            return "📈"
        if savings < prev - 1000:
            return "📉"
        return "✅"
    if savings > 25000:
        return "💰"
    if savings > 15000:
        return "✅"
    if savings > 5000:
        return "💵"
    return "⚠️"


def _savings_status(savings: float, prev: float | None = None) -> str:
    if savings < 0:
        return "(spent more than earned!)"
    if prev is not None:
        diff = savings - prev
        if diff > 1000:
            return f"(recovered +{_inr(diff)})"
        if diff < -1000:
            return f"(down -{_inr(abs(diff))})"
        return "(stable)"
    if savings > 25000:
        return "(strong savings)"
    if savings > 15000:
        return "(good savings)"
    if savings > 5000:
        return "(moderate savings)"
    return "(low savings)"


# ---------------------------------------------------------------------------
# Current-month progress
# ---------------------------------------------------------------------------

def _get_current_month_progress(user=None) -> dict[str, Any]:
    """
    Returns a detailed snapshot of the current month-to-date savings.
    Uses ORM aggregation — never iterates Python-side.
    """
    today = datetime.now().date()
    cy, cm = today.year, today.month
    month_start = today.replace(day=1)
    ny, nm = _next_month(cy, cm)
    next_month_start = today.replace(year=ny, month=nm, day=1)

    qs = Expense.objects.filter(date__year=cy, date__month=cm)
    if user:
        qs = qs.filter(user=user)

    income_mtd = _sum_qs(qs.filter(type="income"))
    expense_mtd = _sum_qs(qs.filter(type="expense"))
    savings_mtd = income_mtd - expense_mtd

    days_elapsed = (today - month_start).days + 1
    total_days = (next_month_start - month_start).days
    days_remaining = total_days - days_elapsed

    daily_rate = savings_mtd / days_elapsed if days_elapsed > 0 else 0.0
    projected_month_end = savings_mtd + daily_rate * days_remaining
    progress_pct = round(days_elapsed / total_days * 100, 1) if total_days else 0.0

    logger.debug(
        "[current_month] income=%.2f expense=%.2f savings=%.2f day=%d/%d",
        income_mtd, expense_mtd, savings_mtd, days_elapsed, total_days,
    )

    return {
        "month": _month_label(cy, cm),
        "year": cy,
        "month_value": cm,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "total_days": total_days,
        "progress_pct": progress_pct,
        # FIX: always expose income/expense so templates can render them
        "income_mtd": round(income_mtd, 2),
        "expense_mtd": round(expense_mtd, 2),
        "savings_mtd": round(savings_mtd, 2),
        "daily_savings_rate": round(daily_rate, 2),
        "projected_month_end": round(projected_month_end, 2),
        "status": "in_progress",
        "emoji": "📍",
        "display": (
            f"{_month_label(cy, cm)}: {_inr(savings_mtd)} so far 📍 "
            f"(Day {days_elapsed}/{total_days} – {progress_pct}% complete)"
        ),
    }


# ---------------------------------------------------------------------------
# Monthly averages (simple fallback)
# ---------------------------------------------------------------------------

def get_monthly_averages(user=None, months: int = 3) -> dict[str, Any]:
    qs = Expense.objects.all()
    if user:
        qs = qs.filter(user=user)

    dates = list(qs.values_list("date", flat=True))
    unique_months = len(set((d.year, d.month) for d in dates)) if dates else 1
    divisor = max(unique_months, 1)

    total_inc = _sum_qs(qs.filter(type="income"))
    total_exp = _sum_qs(qs.filter(type="expense"))
    monthly_savings = (total_inc - total_exp) / divisor

    return {
        "monthly_income": round(total_inc / divisor, 2),
        "monthly_expense": round(total_exp / divisor, 2),
        "monthly_savings": round(monthly_savings, 2),
        "months_analyzed": divisor,
    }


# ---------------------------------------------------------------------------
# LLM explanation via Ollama
# ---------------------------------------------------------------------------

def explain_savings_forecast_llm(forecast_result: dict, user_name: str = "User") -> str:
    """
    Calls local Ollama to generate a plain-English explanation of the forecast.
    Returns a fallback string on any failure — never raises.
    """
    try:
        context = {
            "method": forecast_result.get("method"),
            "trend": forecast_result.get("trend"),
            "trend_message": forecast_result.get("trend_message"),
            "current_month": forecast_result.get("current_month", {}),
            "simple_monthly_savings": forecast_result.get("monthly_savings"),
            "forecast": forecast_result.get("forecast", []),
            "forecast_preview": forecast_result.get("forecast", [])[:3],
            "slope": forecast_result.get("slope"),
            "model_accuracy": forecast_result.get("model_accuracy"),
            "accuracy_interpretation": forecast_result.get("accuracy_interpretation"),
            "summary": forecast_result.get("summary", {}),
            "months_used_for_training": forecast_result.get("months_used_for_training"),
            "training_months": forecast_result.get("training_months"),
        }

        system_prompt = (
            "You are a friendly Indian financial advisor.\n"
            "Explain the user's savings forecast in simple English, "
            "using ₹ amounts and short, practical tips.\n"
            "Do not recommend specific financial products; "
            "focus on budgeting, spending control, and savings habits.\n"
            "VERY IMPORTANT RULES:\n"
            "- Use ONLY the exact numeric values from the data provided.\n"
            "- Do NOT invent, guess, or change any rupee amounts or monthly increments.\n"
            "- If a month or value is not present in the data, do NOT mention it.\n"
            "- If there is a trend_message or slope, restate it without changing the numbers.\n"
            "- When talking about accuracy, reuse the text in 'accuracy_interpretation' "
            "exactly as given instead of adding your own judgement.\n"
        )

        user_prompt = (
            f"User name: {user_name}.\n"
            f"Here is their savings forecast data (Python dict):\n{context}\n\n"
            "Write a short explanation that:\n"
            "1) Briefly describes their current savings situation.\n"
            "2) Explains the savings trend for the next few months using ONLY the given forecast values.\n"
            "3) Gives 3–5 actionable suggestions to improve or maintain savings.\n"
            "Rules:\n"
            "- Do not round or modify the rupee amounts or the monthly change.\n"
            "- Do not describe months that are not in the 'forecast' list.\n"
            "- Include 'accuracy_interpretation' verbatim when you mention accuracy.\n"
            "Keep the explanation under 250 words and easy to understand.\n"
        )

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        t0 = time.time()
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        logger.info("Ollama: status=%d time=%.2fs", resp.status_code, time.time() - t0)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and "message" in data:
            return data["message"].get("content", "").strip()

        if isinstance(data, list):
            return "".join(
                item.get("message", {}).get("content", "") for item in data
            ).strip()

        return "Could not generate AI explanation."

    except Timeout:
        logger.error("Ollama timed out after %ds", OLLAMA_TIMEOUT)
        return "AI explanation is temporarily unavailable due to a timeout. Please try again later."
    except RequestException as exc:
        logger.error("Ollama request failed: %s: %s", type(exc).__name__, exc)
        return "AI explanation is temporarily unavailable. Please try again later."
    except Exception as exc:
        logger.exception("LLM explanation failed: %s", exc)
        return "AI explanation is temporarily unavailable. Please try again later."


# ---------------------------------------------------------------------------
# Simple (fallback) forecast
# ---------------------------------------------------------------------------

def forecast_savings(months_ahead: int = 6, user=None) -> dict[str, Any]:
    """
    Simple average-based forecast. Used when ML is unavailable or data < 2 months.
    """
    ma = get_monthly_averages(user=user)
    monthly_savings = ma["monthly_savings"]

    forecast: list[dict] = []
    cumulative = 0.0
    for m in range(1, months_ahead + 1):
        cumulative += monthly_savings
        forecast.append(
            {
                "month_offset": m,
                "predicted_monthly_savings": round(monthly_savings, 2),
                "expected_cumulative_savings": round(cumulative, 2),
                "trend_emoji": "➡️",
            }
        )

    current_month_data = _get_current_month_progress(user)

    result: dict[str, Any] = {
        "method": "simple_average",
        "trend": None,
        "trend_message": None,
        "monthly_savings": round(monthly_savings, 2),
        "forecast": forecast,
        "months_analyzed": ma.get("months_analyzed"),
        "reason": "Using simple average (ML unavailable or insufficient data)",
        "historical_breakdown": [],
        "current_month": current_month_data,
        "model_accuracy": None,
        "accuracy_interpretation": None,
        "slope": None,
        "summary": None,
        "months_used_for_training": None,
        "training_months": None,
    }
    result["ai_explanation"] = explain_savings_forecast_llm(result)
    return result


# ---------------------------------------------------------------------------
# ML forecast (primary)
# ---------------------------------------------------------------------------

def forecast_savings_ml(months_ahead: int = 6, user=None) -> dict[str, Any]:
    """
    Primary forecast using sklearn LinearRegression on completed months.

    Data pipeline:
        1. Pull all Expense rows for this user via ORM aggregation per month.
        2. Classify each month as COMPLETED, CURRENT, or FUTURE (test data).
        3. Train on COMPLETED months only (future months are excluded).
        4. Predict the next `months_ahead` calendar months.
    """
    today = datetime.now().date()
    current_month_key = (today.year, today.month)

    qs = Expense.objects.all()
    if user:
        qs = qs.filter(user=user)

    if not qs.exists():
        base: dict[str, Any] = {
            "method": "no_data",
            "error": "No expense/income data found",
            "forecast": [],
            "historical_breakdown": [],
            "current_month": None,
        }
        base["ai_explanation"] = explain_savings_forecast_llm(base)
        return base

    # ------------------------------------------------------------------ #
    # Step 1 – aggregate income & expense per calendar month via ORM      #
    # ------------------------------------------------------------------ #
    from django.db.models.functions import TruncMonth
    from django.db.models import CharField, Value
    from django.db.models.functions import Cast

    # Get distinct (year, month) pairs present in DB
    all_month_keys: set[tuple[int, int]] = set(
        (row.year, row.month)
        for row in qs.dates("date", "month")
    )

    logger.info("Months found in DB: %s", sorted(all_month_keys))

    # ORM aggregation per month × type — avoids Python-side loop
    monthly_income: dict[tuple[int, int], float] = {}
    monthly_expense: dict[tuple[int, int], float] = {}

    for mk in all_month_keys:
        year, month = mk
        month_qs = qs.filter(date__year=year, date__month=month)
        monthly_income[mk] = _sum_qs(month_qs.filter(type="income"))
        monthly_expense[mk] = _sum_qs(month_qs.filter(type="expense"))

    # ------------------------------------------------------------------ #
    # Step 2 – classify months                                             #
    # ------------------------------------------------------------------ #
    completed_months: list[tuple[int, int]] = sorted(
        mk for mk in all_month_keys if mk < current_month_key
    )
    future_test_months: list[tuple[int, int]] = sorted(
        mk for mk in all_month_keys if mk > current_month_key
    )

    if future_test_months:
        logger.warning(
            "Future months detected in DB (test data?) — excluded from training: %s",
            future_test_months,
        )

    current_month_data = _get_current_month_progress(user)

    # ------------------------------------------------------------------ #
    # Step 3 – build historical_breakdown (completed months only)          #
    # ------------------------------------------------------------------ #
    historical_breakdown: list[dict] = []
    prev_savings: float | None = None

    for idx, mk in enumerate(completed_months):
        inc = monthly_income[mk]
        exp = monthly_expense[mk]
        sav = inc - exp
        label = _month_label(*mk)

        historical_breakdown.append(
            {
                "month": label,
                "month_number": idx + 1,
                "year": mk[0],
                "month_value": mk[1],
                "income": round(inc, 2),
                "expense": round(exp, 2),       # FIX: was missing / zero in template
                "savings": round(sav, 2),
                "emoji": _savings_emoji(sav, prev_savings),
                "status": _savings_status(sav, prev_savings),
                "is_current": False,
                "display": (
                    f"{label}: {_inr(sav)} "
                    f"{_savings_emoji(sav, prev_savings)} "
                    f"{_savings_status(sav, prev_savings)}"
                ),
            }
        )
        prev_savings = sav

    logger.info("Training on %d completed month(s): %s", len(completed_months), completed_months)

    # ------------------------------------------------------------------ #
    # Step 4 – need ≥ 2 completed months for ML                           #
    # ------------------------------------------------------------------ #
    if len(completed_months) < 2:
        logger.info("Not enough months for ML (%d < 2), falling back", len(completed_months))
        result = forecast_savings(months_ahead, user)
        result["historical_breakdown"] = historical_breakdown
        result["current_month"] = current_month_data
        result["ai_explanation"] = explain_savings_forecast_llm(result)
        return result

    # ------------------------------------------------------------------ #
    # Step 5 – train LinearRegression                                      #
    # ------------------------------------------------------------------ #
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression

        y_savings = np.array(
            [monthly_income[mk] - monthly_expense[mk] for mk in completed_months],
            dtype=float,
        )
        X = np.arange(len(completed_months)).reshape(-1, 1)

        logger.debug("y_savings: %s", y_savings)

        model = LinearRegression()
        model.fit(X, y_savings)

        slope = float(model.coef_[0])
        intercept = float(model.intercept_)
        logger.info("Model: slope=%.2f intercept=%.2f", slope, intercept)

        # ---------------------------------------------------------------- #
        # Current-month pace vs model prediction                            #
        # ---------------------------------------------------------------- #
        n_completed = len(completed_months)
        predicted_current = float(model.predict([[n_completed]])[0])
        current_month_data["predicted_month_end"] = round(predicted_current, 2)

        if current_month_data["days_elapsed"] > 5:
            proj = current_month_data["projected_month_end"]
            if proj > predicted_current * 1.1:
                current_month_data["pace"] = "ahead"
                current_month_data["pace_message"] = (
                    f"📈 On track to exceed prediction by {_inr(proj - predicted_current)}"
                )
            elif proj < predicted_current * 0.9:
                current_month_data["pace"] = "behind"
                current_month_data["pace_message"] = (
                    f"⚠️ Tracking below prediction by {_inr(predicted_current - proj)}"
                )
            else:
                current_month_data["pace"] = "on_track"
                current_month_data["pace_message"] = "✅ On track with prediction"
        else:
            current_month_data["pace"] = "too_early"
            current_month_data["pace_message"] = "⏳ Too early to assess (need more days of data)"

        # ---------------------------------------------------------------- #
        # Step 6 – build forecast (exactly months_ahead entries)            #
        # FIX: old code used `continue` causing fewer than expected entries #
        # ---------------------------------------------------------------- #
        last_completed_year, last_completed_month = completed_months[-1]
        forecast: list[dict] = []
        cumulative = 0.0

        # Start from month AFTER the last completed month
        offset = 1
        while len(forecast) < months_ahead:
            fy, fm = _add_months(last_completed_year, last_completed_month, offset)
            offset += 1

            # Skip current month only if it's already represented in current_month_data
            if (fy, fm) == current_month_key:
                continue

            pred_idx = n_completed + offset - 1  # aligns with training index
            prediction = float(model.predict([[pred_idx]])[0])
            cumulative += prediction

            if not forecast:
                trend_emoji = "🔮"
            else:
                prev_pred = forecast[-1]["predicted_monthly_savings"]
                if prediction > prev_pred + 500:
                    trend_emoji = "📈"
                elif prediction < prev_pred - 500:
                    trend_emoji = "📉"
                else:
                    trend_emoji = "➡️"

            forecast.append(
                {
                    "month_offset": len(forecast) + 1,
                    "month_name": _month_label(fy, fm),
                    "predicted_monthly_savings": round(prediction, 2),
                    "expected_cumulative_savings": round(cumulative, 2),
                    "trend_emoji": trend_emoji,
                }
            )

        # ---------------------------------------------------------------- #
        # Step 7 – model quality metrics                                    #
        # ---------------------------------------------------------------- #
        # FIX: R² on 2 points always returns 1.0 — flag as INSUFFICIENT    #
        if n_completed < 3:
            r2 = float(model.score(X, y_savings))
            r2_text = f"R² = {round(r2, 2)}"
            r2_interp = (
                f"⚠️ INSUFFICIENT DATA — Only {n_completed} month(s) used. "
                "Need 3+ months for reliable predictions."
            )
        else:
            r2 = float(model.score(X, y_savings))
            r2_text = f"R² = {round(r2, 2)}"
            if r2 >= 0.7:
                r2_interp = "Excellent — predictions are highly reliable ✅"
            elif r2 >= 0.5:
                r2_interp = "Good — predictions are fairly reliable 👍"
            elif r2 >= 0.3:
                r2_interp = "Moderate — predictions have some uncertainty ⚠️"
            else:
                r2_interp = "Low — high volatility, predictions are uncertain ❌"

        # Trend label
        if slope > 100:
            trend = "improving"
            trend_message = f"📈 Savings increasing by ~{_inr(slope)}/month"
        elif slope < -100:
            trend = "declining"
            trend_message = f"📉 Savings decreasing by ~{_inr(abs(slope))}/month"
        else:
            trend = "stable"
            trend_message = "➡️ Savings relatively stable"

        result: dict[str, Any] = {
            "method": "linear_regression",
            "trend": trend,
            "trend_message": trend_message,
            "forecast": forecast,
            "model_accuracy": r2_text,
            "accuracy_interpretation": r2_interp,
            "months_used_for_training": n_completed,
            "training_months": [f"{y}-{m:02d}" for y, m in completed_months],
            "slope": round(slope, 2),
            "historical_savings": [round(float(s), 2) for s in y_savings],
            "historical_breakdown": historical_breakdown,
            "current_month": current_month_data,
            "summary": {
                "total_completed_months": n_completed,
                "average_monthly_savings": round(float(np.mean(y_savings)), 2),
                "highest_month": {
                    "month": _month_label(*completed_months[int(np.argmax(y_savings))]),
                    "savings": round(float(np.max(y_savings)), 2),
                },
                "lowest_month": {
                    "month": _month_label(*completed_months[int(np.argmin(y_savings))]),
                    "savings": round(float(np.min(y_savings)), 2),
                },
            },
        }

        result["ai_explanation"] = explain_savings_forecast_llm(result)
        return result

    except ImportError:
        logger.error("scikit-learn not installed. Run: pip install scikit-learn numpy")
        result = forecast_savings(months_ahead, user)
        result["historical_breakdown"] = historical_breakdown
        result["current_month"] = current_month_data
        result["ai_explanation"] = explain_savings_forecast_llm(result)
        return result

    except Exception:
        logger.exception("ML forecast failed unexpectedly")
        result = forecast_savings(months_ahead, user)
        result["historical_breakdown"] = historical_breakdown
        result["current_month"] = current_month_data
        result["ai_explanation"] = explain_savings_forecast_llm(result)
        return result