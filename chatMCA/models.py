# chatMCA/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class ChatSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id[:8]} - {self.title or 'Untitled'}"
    
    def get_title(self):
        """Generate title from first message if not set"""
        if self.title:
            return self.title
        first_message = self.messages.first()
        if first_message:
            return first_message.user_message[:50] + "..." if len(first_message.user_message) > 50 else first_message.user_message
        return "New Conversation"
    
    def message_count(self):
        return self.messages.count()

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    user_message = models.TextField()
    ai_response = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    response_time = models.FloatField(default=0.0)  # API response time in seconds
    tokens_used = models.IntegerField(default=0, blank=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Message in {self.session.session_id[:8]} at {self.timestamp}"

class ChatAnalytics(models.Model):
    date = models.DateField(unique=True)
    total_messages = models.IntegerField(default=0)
    total_sessions = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    total_tokens = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"Analytics for {self.date}"
