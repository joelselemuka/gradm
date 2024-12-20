# Generated by Django 5.1.2 on 2024-11-03 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UniteVente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unit', models.CharField(max_length=250)),
                ('unitTag', models.CharField(max_length=5)),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Date de creation')),
                ('status', models.BooleanField(default=True, verbose_name='Status')),
            ],
            options={
                'verbose_name': 'UniteVente',
                'verbose_name_plural': 'UniteVentes',
                'db_table': 't_UniteVente',
                'managed': True,
            },
        ),
    ]
