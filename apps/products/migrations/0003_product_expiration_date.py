from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0002_productvariant_barcodes")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="expiration_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
