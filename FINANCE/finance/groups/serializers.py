from rest_framework import serializers
from .models import Group, GroupMember, GroupExpense, GroupMessage, ExpenseSplit, SplitAnalysis
from users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username')


class GroupMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = GroupMessage
        fields = ('id', 'group', 'sender', 'message', 'created_at')
        read_only_fields = ('id', 'sender', 'created_at')


class ExpenseSplitSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ('id', 'expense', 'user', 'suggested_amount', 'adjusted_amount', 'final_amount', 'status', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class SplitAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SplitAnalysis
        fields = ('id', 'group', 'expense', 'analysis_data', 'algorithm_version', 'created_at')
        read_only_fields = ('id', 'created_at')


class GroupExpenseDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)

    class Meta:
        model = GroupExpense
        fields = ('id', 'group', 'user', 'amount', 'description', 'date', 'splits', 'created_at')


class GroupSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'created_by', 'created_at')


class GroupMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = ['id', 'group', 'user', 'joined_at']


class GroupExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupExpense
        fields = ['id', 'group', 'user', 'amount', 'description', 'date', 'created_at']
