from django.db import models
from users.models import User

class Goal(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('paused', 'Paused'),
    ]
    
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    target_amount = models.FloatField()
    amount_saved = models.FloatField(default=0)
    priority = models.IntegerField(default=5)  # 1-10 scale (higher = higher priority)
    deadline = models.DateField()
    duration_days = models.IntegerField(default=0)  # Estimated days to complete goal (for feasibility sorting)
    original_deadline = models.DateField(null=True, blank=True)  # Track original deadline if adjusted
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ₹{self.amount_saved}/₹{self.target_amount}"
    
    class Meta:
        ordering = ['-priority', 'duration_days', 'deadline']  # Sort by priority DESC, then duration ASC, then deadline