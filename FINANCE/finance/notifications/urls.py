from django.urls import path
from .views import (
    NotificationListHTML, NotificationDetailHTML
)

urlpatterns = [

    # HTML ROUTES
    path('list/', NotificationListHTML.as_view(), name='notification-list-html'),
    path('<int:pk>/view/', NotificationDetailHTML.as_view(), name='notification-detail-html'),

   
]
