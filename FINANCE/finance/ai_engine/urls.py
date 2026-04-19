# ai_engine/urls.py
"""
AI ENGINE URL CONFIGURATION
Each endpoint has both API (JSON) and HTML (template) variants.

URL Patterns:
- /ai/overspending/         -> HTML view (default)
- /ai/overspending/api/     -> JSON API
- /ai/alerts/               -> HTML view (default)
- /ai/alerts/api/           -> JSON API
... and so on for all endpoints
"""

from django.urls import path
from . import views

app_name = "ai_engine"

urlpatterns = [
    # =============================================================================
    # OVERSPENDING
    # =============================================================================
    path("overspending/", views.overspending_html, name="overspending"),
    path("overspending/api/", views.overspending_api, name="overspending-api"),

    # =============================================================================
    # ALERTS
    # =============================================================================
    path("alerts/", views.alerts_html, name="alerts"),
    path("alerts/api/", views.alerts_api, name="alerts-api"),

    # =============================================================================
    # SUGGESTIONS
    # =============================================================================
    path("suggestions/", views.suggestions_html, name="suggestions"),
    path("suggestions/api/", views.suggestions_api, name="suggestions-api"),

    # =============================================================================
    # CLUSTERING
    # =============================================================================
    path("clustering/", views.clustering_html, name="clustering"),
    path("clustering/api/", views.clustering_api, name="clustering-api"),

    # =============================================================================
    # STRATEGY
    # =============================================================================
    path("strategy/", views.strategy_html, name="strategy"),
    path("strategy/api/", views.strategy_api, name="strategy-api"),

    # =============================================================================
    # FORECAST
    # =============================================================================
    path("forecast/", views.forecast_html, name="forecast"),
    path("forecast/api/", views.forecast_api, name="forecast-api"),

    # =============================================================================
    # INSIGHTS
    # =============================================================================
    path("insights/", views.insights_html, name="insights"),
    path("insights/api/", views.insights_api, name="insights-api"),

    # =============================================================================
    # FEASIBILITY (Single Goal)
    # =============================================================================
    path("feasibility/<int:pk>/", views.feasibility_html, name="feasibility"),
    path("feasibility/<int:pk>/api/", views.feasibility_api, name="feasibility-api"),

    # =============================================================================
    # FEASIBILITY (Multi-Goal)
    # =============================================================================
    path("feasibility/multi/", views.feasibility_multi_html, name="feasibility-multi"),
    path("feasibility/expired/", views.feasibility_expired_html, name="feasibility-expired"),
    path("feasibility/multi/api/", views.feasibility_multi_api, name="feasibility-multi-api"),

    # =============================================================================
    # MONTHLY AVERAGES / ANALYSIS
    # =============================================================================
    path("monthly/", views.monthly_html, name="monthly"),
    path("monthly/api/", views.monthly_averages_api, name="monthly-api"),
    path("monthly-averages/", views.monthly_averages_api, name="monthly-averages"),

    # =============================================================================
    # AI ENGINE (MASTER)
    # =============================================================================
    path("engine/", views.ai_engine_html, name="ai-engine"),
    path("engine/api/", views.ai_engine_api, name="ai-engine-api"),
    path("master/", views.ai_engine_api, name="master-api"),
    path("master/html/", views.ai_engine_html, name="master-html"),

    # =============================================================================
    # UTILITY
    # =============================================================================
    path("optimize/", views.feasibility_multi_api, name="optimize-goals"),
]
