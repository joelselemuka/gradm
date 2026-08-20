from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]

    operations = [
        migrations.AddField(model_name="productvariant", name="manufacturer_barcode", field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True)),
        migrations.AddField(model_name="productvariant", name="store_barcode", field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True)),
    ]
