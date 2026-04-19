from django.urls import path
from .views import UserRegisterHTML, UserListHTML, UserDetailHTML, DashboardHTML, ToggleAIView, LoginHTML, logout_view
from . import views
urlpatterns = [
       # HTML TEMPLATE ROUTES
    path('register/', UserRegisterHTML.as_view(), name='user-register-html'),
    path('list/', UserListHTML.as_view(), name='user-list-html'),
    path('<int:pk>/view/', UserDetailHTML.as_view(), name='user-detail-html'),
    path('dashboard/', DashboardHTML.as_view(), name='user-dashboard'),
    path("toggle-ai/",  views.ToggleAIView.as_view(),       name="toggle-ai"),  # ← ADD HERE
    path('login/', LoginHTML.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    
]
