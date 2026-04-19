from django.urls import path
from .views import (
    AnalyticsSummaryHTML, AnalyticsMonthlyHTML, AnalyticsCategoryHTML
)

urlpatterns = [

    # HTML pages
    path('summary/', AnalyticsSummaryHTML.as_view(), name='analytics-summary-html'),
    path('monthly/', AnalyticsMonthlyHTML.as_view(), name='analytics-monthly-html'),
    path('categories/', AnalyticsCategoryHTML.as_view(), name='analytics-category-html'),

]
