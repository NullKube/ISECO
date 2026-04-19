from django.db import models
from users.models import User

class Group(models.Model):
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_groups")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"


class GroupExpense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.FloatField()
    description = models.CharField(max_length=255)
    date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} by {self.user.username} in {self.group.name}"


class GroupInvite(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invites")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_group_invites")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_group_invites")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.receiver.username} invited to {self.group.name} by {self.sender.username}"


class GroupMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_messages")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['group', '-created_at']),
        ]

    def __str__(self):
        return f"{self.sender.username} in {self.group.name}: {self.message[:50]}"


class ExpenseSplit(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("settled", "Settled"),
    ]

    expense = models.ForeignKey(GroupExpense, on_delete=models.CASCADE, related_name="splits")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    suggested_amount = models.FloatField()
    adjusted_amount = models.FloatField(null=True, blank=True)
    final_amount = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('expense', 'user')

    def __str__(self):
        return f"Split for {self.user.username}: ₹{self.final_amount}"


class SplitAnalysis(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="split_analyses")
    expense = models.ForeignKey(GroupExpense, on_delete=models.CASCADE, null=True, blank=True, related_name="analyses")
    analysis_data = models.JSONField()
    algorithm_version = models.CharField(max_length=50, default="v1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Split Analyses"

    def __str__(self):
        return f"Analysis for Expense {self.expense.id} in {self.group.name}"
