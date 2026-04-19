from django.db import models

class User(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # plain for now

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username
