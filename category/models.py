from django.db import models

# Create your models here.
class Categorie(models.Model):
    CHOICES=(
        ('Activée', 'Activée '),
        ('Désactivée', 'Désactivée')
    )
    Name = models.CharField(max_length=250,unique=True,verbose_name="Catégorie")
    Status=models.CharField(max_length=250,verbose_name="Statut",choices=CHOICES)
    Created=models.DateTimeField(auto_now_add=True,verbose_name="Date de creation")
    def __str__(self):
        return self.Name

    class Meta:
        db_table = 'db_Categorie'
        managed = True
        verbose_name = 'Categorie'
        verbose_name_plural = 'Categories'