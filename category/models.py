from django.db import models

# Create your models here.
class Categorie(models.Model):
    name = models.CharField(max_length=250,unique=True,verbose_name="Catégorie")
    status=models.BooleanField(default=True, verbose_name="Status")
    created_at=models.DateField(auto_now_add=True,verbose_name="Date de creation")
    def __str__(self):
        return self.name

    class Meta:
        db_table = 't_Categorie'
        managed = True
        verbose_name = 'Categorie'
        verbose_name_plural = 'Categories'