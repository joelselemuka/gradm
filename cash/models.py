from django.db import models

# Create your models here.

class Cash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    estConfirme= models.BooleanField(default=False)

    def __str__(self):
        return self.date

    class Meta:
        db_table = 't_Cash'
        managed = True
        verbose_name = 'Cash'
        verbose_name_plural = 'Cash'


class EntreeCash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    motif = models.TextField()
    cash = models.ForeignKey(Cash, on_delete=models.CASCADE)
    estConfirme= models.BooleanField(default=False)

    def __str__(self):
        return self.date

    class Meta:
        db_table = 't_Entree_Stock'
        managed = True
        verbose_name = 'Entree_stock'
        verbose_name_plural = 'Entree_stocks'

class SortieCash(models.Model):
    date = models.DateField()
    montant= models.PositiveBigIntegerField()
    motif = models.TextField()
    cash = models.ForeignKey(Cash, on_delete=models.CASCADE)
    estConfirme= models.BooleanField(default=False)

    def __str__(self):
        return self.date

    class Meta:
        db_table = 't_Sortie_Stock'
        managed = True
        verbose_name = 'Sortie_stock'
        verbose_name_plural = 'Sortie_stocks'