from django.db import models

# Create your models here.
from django.db import models
from category.models import Categorie
# Create your models here.



class UniteVente(models.Model):
   
    unit = models.CharField(max_length=250)
    unitTag = models.CharField(max_length=5)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Date de creation")
    status=models.BooleanField(default=True, verbose_name="Status")
    def __str__(self):
        return f'{self.unit}-{self.unitTag}'

    class Meta:
        db_table = 't_UniteVente'
        managed = True
        verbose_name = 'UniteVente'
        verbose_name_plural = 'UniteVentes'

class Product(models.Model):
    CHOICES=(
        ('Simple', 'Simple '),
        ('Varié', 'Varié')
    )
    codeRef=models.CharField(max_length=8)
    libelle = models.TextField(max_length=400)
    unity=models.ForeignKey(UniteVente,on_delete=models.CASCADE)
    qteEnVente=models.PositiveIntegerField(verbose_name="Qté en vente", default=1)
    productType=models.CharField(verbose_name="Type de produit", max_length=50,choices=CHOICES)
    barreCode=models.CharField(verbose_name="Barre Code", max_length=50)
    stockAlert=models.IntegerField(verbose_name="Stock alerte", default=5)
    canExpiried=models.BooleanField(default=False)
    pu=models.FloatField(verbose_name="Prix de vente")
    manuf_on=models.DateTimeField()
    expiried_on=models.DateTimeField()
    categorie=models.ForeignKey(Categorie,on_delete=models.CASCADE)
    status = models.BooleanField(default=True, verbose_name="Status")
    def __str__(self):
        return f'{self.codeRef}-{self.libelle}-{self.qteEnVente}{self.unity}'

    class Meta:
        db_table = 't_Product'
        managed = True
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

class ProductCodeBarre(models.Model):
    codeBarre=models.CharField(max_length=30)
    status = models.BooleanField(default=True, verbose_name="Status")
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return self.Product.libelle

    class Meta:
        db_table = 't_ProductCodeBarre'
        managed = True
        verbose_name = 'ProductCodeBarre'
        verbose_name_plural = 'ProductCodeBarres'
