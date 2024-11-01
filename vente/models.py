from datetime import datetime

from django.db import models
from django.contrib.auth.models import User

# Create your models here.
from article.models import Product
from django.contrib.auth import get_user_model

user = get_user_model()


class Caisse(models.Model):
    name = models.CharField(max_length=100)
    EstOuvert = models.BooleanField(default=False)
    login = models.ForeignKey(user, on_delete=models.CASCADE)
    LastDateOpen = models.DateTimeField()
    LastDateClose = models.DateTimeField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'db_Caisse'
        managed = True
        verbose_name = 'Caisse'
        verbose_name_plural = 'Caisses'


class Vente(models.Model):
    dateVente = models.DateField()
    total_franc = models.IntegerField()
    total_dollar = models.IntegerField()

class Depense(models.Model):
    motif= models.TextField(verbose_name="Motif de dépense")
    montant_franc = models.IntegerField()
    montant_dollar = models.IntegerField()
    vente= models.ForeignKey(Vente, on_delete=models.CASCADE)

class Facture(models.Model):
    utilisateur = models.ForeignKey(user, on_delete=models.CASCADE)
    numFacture = models.CharField(verbose_name="N° Facture")
    dateFacture = models.DateTimeField(auto_now_add=True)
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE)
    product = models.ManyToManyField(Product, through='LigneFacture', related_name='Product_fact_Items')
    total = models.IntegerField(default=0)
    remise = models.IntegerField(default=0)
    netPaye = models.IntegerField(default=0)

    def __str__(self):
        return self.numFacture

    def save(self, *args, **kwargs):
        self.dateFacture = datetime.now()
        super(Facture, self).save(*args, **kwargs)

    class Meta:
        db_table = 'db_Facture'
        managed = True
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'


class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.IntegerField(default=0)
    prix = models.IntegerField(default=0)
    total = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.facture.numFacture}--{self.product.libelle}'

    class Meta:
        db_table = 'db_LigneFacture'
        managed = True
        verbose_name = 'LigneFacture'
        verbose_name_plural = 'LigneFactures'
