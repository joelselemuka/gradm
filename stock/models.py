from django.db import models
from article.models import Product
from time import  timezone
from datetime import datetime
# Create your models here.
class Stock(models.Model):
    Qty=models.IntegerField(default=0)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.Product.Name}--{self.Qty}'

    class Meta:
        db_table = 'db_Stock'
        managed = True
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'

class Approvisionnement(models.Model):
    DateAppro=models.DateTimeField(auto_now_add=True)
    Product=models.ManyToManyField(Product,through='DetailAppro',related_name='Product_Appro_Items')
    def __str__(self):
        return f'Approvisionnement du {self.DateAppro}'

    def save(self, *args, **kwargs):
        self.DateAppro = datetime.now()
        super(Approvisionnement, self).save(*args, **kwargs)
    class Meta:
        db_table = 'db_Approvisionnement'
        managed = True
        verbose_name = 'Approvisionnement'
        verbose_name_plural = 'Approvisionnements'

class DetailAppro(models.Model):
    Qty=models.IntegerField(default=0)
    Appro=models.ForeignKey(Approvisionnement,on_delete=models.CASCADE)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.Appro.DateAppro}--{self.Product.Name}--{self.Qty}'

    class Meta:
        db_table = 'db_DetailAppro'
        managed = True
        verbose_name = 'DetailAppro'
        verbose_name_plural = 'DetailAppros'



# SORTIES STOCK
class SortieStock(models.Model):
    DateSortie=models.DateTimeField(auto_now_add=True)
    Product=models.ManyToManyField(Product,through='DetailSortie',related_name='Product_Sortie_Items')
    def __str__(self):
        return f'Sortie du {self.DateAppro}'

    def save(self, *args, **kwargs):
        self.DateSortie = datetime.now()
        super(SortieStock, self).save(*args, **kwargs)

    class Meta:
        db_table = 'db_SortieStock'
        managed = True
        verbose_name = 'SortieStock'
        verbose_name_plural = 'SortieStocks'

class DetailSortie(models.Model):
    Qty=models.IntegerField(default=0)
    Sortie=models.ForeignKey(SortieStock,on_delete=models.CASCADE)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE)
    def __str__(self):
        return f'{self.Sortie.DateSortie}--{self.Product.Name}--{self.Qty}'

    class Meta:
        db_table = 'db_DetailSortie'
        managed = True
        verbose_name = 'DetailSortie'
        verbose_name_plural = 'DetailSorties'

