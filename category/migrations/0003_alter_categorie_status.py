# Generated by Django 5.0.6 on 2024-05-17 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('category', '0002_alter_categorie_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorie',
            name='Status',
            field=models.CharField(choices=[('Activée', 'Activée '), ('Désactivée', 'Désactivée')], max_length=250, verbose_name='Statut'),
        ),
    ]
