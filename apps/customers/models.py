from django.db import models
class Customer(models.Model):
    name=models.CharField(max_length=160,db_index=True)
    phone=models.CharField(max_length=40,blank=True,db_index=True)
    email=models.EmailField(blank=True)
    address=models.TextField(blank=True)
    active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
