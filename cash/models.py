from django.db import models

# Create your models here.

class Cash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    estConfirme= models.BooleanField(default=False)


class EntreeCash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    motif = models.TextField()
    cash = models.ForeignKey(Cash, on_delete=models.CASCADE)
    estConfirme= models.BooleanField(default=False)

class SortieCash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    motif = models.TextField()
    cash = models.ForeignKey(Cash, on_delete=models.CASCADE)
    estConfirme= models.BooleanField(default=False)
