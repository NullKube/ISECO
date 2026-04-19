from django.urls import path
from .views import (
    GoalAddHTML,
    GoalListHTML,
    GoalDetailHTML,
    GoalEditHTML,
    ConfirmShiftAPI,
    MarkAchievedAPI,
    OptimizeGoalsByPriorityAPI,
    CheckGoalFeasibilityAPI,
    ConfirmGoalCreationAPI,
)

urlpatterns = [

    # HTML TEMPLATE ROUTES
    path('add/', GoalAddHTML.as_view(), name='goal-add-html'),
    path('list/', GoalListHTML.as_view(), name='goal-list-html'),
    path('<int:pk>/view/', GoalDetailHTML.as_view(), name='goal-detail-html'),
    path('<int:pk>/edit/', GoalEditHTML.as_view(), name='goal-edit'),

    # FEASIBILITY CHECK API (before goal creation)
    path('api/check-feasibility/', CheckGoalFeasibilityAPI.as_view(), name='check-feasibility'),
    path('api/confirm-creation/', ConfirmGoalCreationAPI.as_view(), name='confirm-goal-creation'),

    # DASHBOARD API ROUTES
    path('<int:pk>/confirm-shift/', ConfirmShiftAPI.as_view(), name='confirm-shift'),
    path('<int:pk>/mark-achieved/', MarkAchievedAPI.as_view(), name='mark-achieved'),
    path('api/optimize-by-priority/', OptimizeGoalsByPriorityAPI.as_view(), name='optimize-by-priority'),
]
