from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import generics

from .models import Notification
from .serializers import NotificationSerializer
from users.models import User


class NotificationListHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "notifications_list.html"

    def get(self, request):
        notifications = Notification.objects.all().order_by("-created_at")
        return Response({"notifications": notifications})


class NotificationDetailHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "notification_detail.html"

    def get(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk)
        if not notif.is_read:
            notif.is_read = True
            notif.save()
        return Response({"notif": notif})
