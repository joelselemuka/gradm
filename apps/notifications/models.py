from django.conf import settings
from django.db import models
class Notification(models.Model):
    class Level(models.TextChoices): INFO="INFO","Information"; WARNING="WARNING","Alerte"; ERROR="ERROR","Critique"
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="notifications")
    level=models.CharField(max_length=10,choices=Level.choices,default=Level.INFO)
    title=models.CharField(max_length=160); message=models.TextField(); target_url=models.CharField(max_length=500, blank=True); read_at=models.DateTimeField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]
