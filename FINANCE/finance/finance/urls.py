from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # USERS APP
    path('users/', include('users.urls')),

    # EXPENSES APP
    path('expenses/', include('expenses.urls')),

    # GOALS APP
    path('goals/', include('goals.urls')),

    # ANALYTICS APP
    path('analytics/', include('analytics.urls')),

    # AI ENGINE APP
    path('ai/', include('ai_engine.urls')),

    # GROUPS APP
    path('groups/', include('groups.urls')),

    # NOTIFICATIONS APP (you will add next)
    path('notifications/', include('notifications.urls')),
]
