# Generated by Django 5.1.2 on 2024-11-03 14:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('unity', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unitevente',
            name='unit',
            field=models.CharField(max_length=250, unique=True, verbose_name='Unité'),
        ),
        migrations.AlterField(
            model_name='unitevente',
            name='unitTag',
            field=models.CharField(max_length=3, unique=True),
        ),
    ]
