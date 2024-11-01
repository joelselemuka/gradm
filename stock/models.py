from django.db import models
from article.models import Product
from time import  timezone
from datetime import datetime
# Create your models here.
class Stock(models.Model):
    qty=models.IntegerField(default=0, verbose_name="Qté en stock")
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.Product.Name}--{self.Qty}'

    class Meta:
        db_table = 'db_Stock'
        managed = True
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'

class Entree(models.Model):
    dateEntree=models.DateTimeField(auto_now_add=True)
    Product=models.ManyToManyField(Product,through='DetailAppro',related_name='Product_Appro_Items')
    def __str__(self):
        return f'Enttée stock du {self.dateEntree}'

    def save(self, *args, **kwargs):
        self.dateEntree = datetime.now()
        super(Entree, self).save(*args, **kwargs)
    class Meta:
        db_table = 'db_Entree'
        managed = True
        verbose_name = 'Entrée'
        verbose_name_plural = 'Entées'

class DetailAppro(models.Model):
    qty=models.IntegerField(default=0)
    entree=models.ForeignKey(Entree,on_delete=models.CASCADE)
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.entree.dateEntree}--{self.product.libelle}'

    class Meta:
        db_table = 'db_DetailAppro'
        managed = True
        verbose_name = 'DetailAppro'
        verbose_name_plural = 'DetailAppros'



# SORTIES STOCK
class SortieStock(models.Model):
    dateSortie=models.DateTimeField(auto_now_add=True)
    motif = models.TextField(verbose_name="Motif de sortie")
    product=models.ManyToManyField(Product,through='DetailSortie',related_name='Product_Sortie_Items')
    def __str__(self):
        return f'Sortie du {self.dateSortie}'

    def save(self, *args, **kwargs):
        self.dateSortie = datetime.now()
        super(SortieStock, self).save(*args, **kwargs)

    class Meta:
        db_table = 'db_SortieStock'
        managed = True
        verbose_name = 'SortieStock'
        verbose_name_plural = 'SortieStocks'

class DetailSortie(models.Model):
    qty=models.IntegerField(default=0)
    sortie=models.ForeignKey(SortieStock,on_delete=models.CASCADE)
    product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.sortie.dateSortie}--{self.product.libelle}'

    class Meta:
        db_table = 'db_DetailSortie'
        managed = True
        verbose_name = 'DetailSortie'
        verbose_name_plural = 'DetailSorties'

