from django.db import models

# Create your models here.
from django.db import models
from category.models import Categorie
from unity.models import UniteVente


# Create your models here.


class Product(models.Model):
    CHOICES = (
        ('Simple', 'Simple '),
        ('Varié', 'Varié')
    )

    libelle = models.CharField(max_length=255, verbose_name="Libellé", unique=True)
    unity = models.ForeignKey(UniteVente, on_delete=models.CASCADE)
    productType = models.CharField(verbose_name="Type de produit", max_length=50, choices=CHOICES)
    stockAlert = models.IntegerField(verbose_name="Stock alerte", default=5)
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE)
    description = models.TextField(verbose_name="Déscription", blank=True, null=True)

    def __str__(self):
        return {self.libelle}

    class Meta:
        db_table = 't_Product'
        managed = True
        verbose_name = 'Product'
        verbose_name_plural = 'Products'


class Variantes(models.Model):
    codeRef = models.CharField(max_length=8, verbose_name="Code", unique=True)
    varianteValue = models.CharField(max_length=200, verbose_name="Variante")
    qteEnVente = models.PositiveIntegerField(verbose_name="Qté en vente", default=1)
    pu = models.PositiveIntegerField(verbose_name="Prix de vente", default=0)
    canExpiried = models.BooleanField(default=False)
    expiried_on = models.DateField()
    barreCode = models.CharField(verbose_name="Barre Code", max_length=50)
    status = models.BooleanField(default=True, verbose_name="Status")
    created_at = models.DateField(auto_now_add=True, verbose_name="Date de creation")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.product.libelle} {self.varianteValue} {self.product.unity}'

    class Meta:
        db_table = 't_Variante'
        managed = True
        verbose_name = 'Variante'
        verbose_name_plural = 'Variantes'


class ProductCodeBarre(models.Model):
    codeBarre = models.CharField(max_length=30)
    status = models.BooleanField(default=True, verbose_name="Status")
    product = models.ForeignKey(Variantes, on_delete=models.CASCADE)

    def __str__(self):
        return self.product.libelle

    class Meta:
        db_table = 't_ProductCodeBarre'
        managed = True
        verbose_name = 'ProductCodeBarre'
        verbose_name_plural = 'ProductCodeBarres'