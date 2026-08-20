from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="stockmovement",
            name="movement_type",
            field=models.CharField(choices=[("RECEIPT", "Réception"), ("SALE", "Vente"), ("SALE_CANCELLED", "Annulation vente"), ("RETURN", "Retour"), ("ADJUSTMENT", "Ajustement"), ("STOCK_OUT", "Sortie de stock"), ("LOSS", "Perte"), ("EXPIRY", "Expiration")], max_length=24),
        ),
    ]
