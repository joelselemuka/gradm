# Generated by Django 5.1.2 on 2024-11-03 14:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('unity', '0002_alter_unitevente_unit_alter_unitevente_unittag'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unitevente',
            name='created',
            field=models.DateField(auto_now_add=True, verbose_name='Date de creation'),
        ),
    ]
