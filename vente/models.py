from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class Caisse(models.Model):
    name=models.CharField(max_length=100)
    EstOuvert=models.BooleanField(default=False)
    login=models.ForeignKey(User,on_delete=models.CASCADE)
    LastDateOpen=models.DateTimeField()
    LastDateClose=models.DateTimeField()
    def __str__(self):
        return self.name

    class Meta:
        db_table = 'db_Caisse'
        managed = True
        verbose_name = 'Caisse'
        verbose_name_plural = 'Caisses'



