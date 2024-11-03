from django.db import models

# Create your models here.

class UniteVente(models.Model):
    unit = models.CharField(max_length=250, unique=True, verbose_name="Unité")
    unitTag = models.CharField(max_length=3, unique=True)
    created = models.DateField(auto_now_add=True, verbose_name="Date de creation")
    status = models.BooleanField(default=True, verbose_name="Status")

    def __str__(self):
        return f'{self.unit}-{self.unitTag}'

    class Meta:
        db_table = 't_UniteVente'
        managed = True
        verbose_name = 'UniteVente'
        verbose_name_plural = 'UniteVentes'

