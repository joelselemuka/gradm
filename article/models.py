from django.db import models

# Create your models here.
from django.db import models
from category.models import Categorie
# Create your models here.

CHOICES=(
        ('Activée', 'Activée '),
        ('Désactivée', 'Désactivée')
    )

class UniteVente(models.Model):
   
    Unit = models.CharField(max_length=250)
    UnitTag = models.CharField(max_length=5)
    Created = models.DateTimeField(auto_now_add=True, verbose_name="Date de creation")
    Status=models.CharField(max_length=250,verbose_name="Statut",choices=CHOICES)
    def __str__(self):
        return self.Unit

    class Meta:
        db_table = 'db_UniteVente'
        managed = True
        verbose_name = 'UniteVente'
        verbose_name_plural = 'UniteVentes'

class Product(models.Model):
    CHOICES=(
        ('Simple', 'Simple '),
        ('Varié', 'Varié')
    )
    Code=models.CharField(max_length=8)
    Name = models.TextField(max_length=400)
    Marque=models.CharField(max_length=150)
    Unite=models.ForeignKey(UniteVente,on_delete=models.CASCADE)
    QtyValue=models.PositiveIntegerField()
    ProductType=models.CharField(verbose_name="Type produit", max_length=50,choices=CHOICES)
    BarreCode=models.CharField(verbose_name="Barre Code", max_length=50)
    StockAlert=models.IntegerField()
    Expiry=models.BooleanField(default=False)
    PrixVente=models.FloatField()
    DateFab=models.DateTimeField()
    DateExp=models.DateTimeField()
    Categorie=models.ForeignKey(Categorie,on_delete=models.CASCADE)
    Status=models.CharField(max_length=250,verbose_name="Statut",choices=CHOICES)
    def __str__(self):
        return f'{self.Code} - {self.Name} - {self.QtyValue} {self.Unite}'

    class Meta:
        db_table = 'db_Product'
        managed = True
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

class ProductCodeBarre(models.Model):
    CodeBarre=models.CharField(max_length=30)
    Status=models.CharField(max_length=250,verbose_name="Statut",choices=CHOICES)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.Product.Name}--{self.CodeBarre}'

    class Meta:
        db_table = 'db_ProductCodeBarre'
        managed = True
        verbose_name = 'ProductCodeBarre'
        verbose_name_plural = 'ProductCodeBarres'
