from rest_framework import serializers
from .models import Goal

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            'id', 'user', 'target_amount', 'priority',
            'deadline', 'amount_saved', 'status', 'created_at'
        ]
