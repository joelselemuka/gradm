from django.db import models


# Create your models here.

class Personnel(models.Model):
    STATUT = (
        ('ENGAGE', 'ENGAGE '),
        ('DEMISIONNE', 'DEMISSINNE'),
        ('LICENCIE', 'LICENCIE'),
    )
    nom = models.CharField(verbose_name="Nom", max_length=255)
    postnom = models.CharField(verbose_name="Post-nom", max_length=255)
    prenom = models.CharField(verbose_name="Prénom", max_length=255)
    fonction = models.CharField(verbose_name="Fonction", max_length=255)
    salaire = models.IntegerField(verbose_name="Salaire")
    date_embauche = models.DateField(verbose_name="Date d'embauche")
    statut = models.CharField(verbose_name="Statut", max_length=100, choices=STATUT, default="ENGAGE")

    def __str__(self):
        return f'{self.nom}- {self.postnom}- {self.prenom}'
class Credit(models.Model):
    personnel=models.ForeignKey(Personnel, on_delete=models.CASCADE)
    montant= models.IntegerField(default=0)




class Paie(models.Model):
    periode= models.DateField()
    personnel = models.ManyToManyField(Personnel, through='FichePaie', related_name='details_paie')
    estPaye= models.BooleanField(default=False)


    def __str__(self):
        return self.periode

    class Meta:
        db_table = 't_Paie'
        managed = True
        verbose_name = 'Paie'
        verbose_name_plural = 'Paies'

class FichePaie(models.Model):
    totalAbsences = models.IntegerField(default=0)
    penaliteAbsences = models.IntegerField(default=0)
    totalCredit = models.IntegerField(default=0)
    totalRetenu = models.IntegerField(default=0)
    netApayer = models.IntegerField(default=0)
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE)
    paie = models.ForeignKey(Paie, on_delete=models.CASCADE)

    def __str__(self):
        return self.personnel.nom

    class Meta:
        db_table = 't_Fiche_paie'
        managed = True
        verbose_name = 'Fiche_paie'
        verbose_name_plural = 'Fiche_paies'


class Absence(models.Model):
    fichePaie= models.ForeignKey(FichePaie, on_delete=models.CASCADE)
    nombre = models.IntegerField(default=0)
    def __str__(self):
        return self.fichePaie.personnel.nom

    class Meta:
        db_table = 't_Absence'
        managed = True
        verbose_name = 'Absence'
        verbose_name_plural = 'Absences'