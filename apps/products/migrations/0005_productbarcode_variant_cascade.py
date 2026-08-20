import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("products", "0004_productbarcode")]
    operations = [migrations.AlterField(model_name="productbarcode", name="variant", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="barcode_aliases", to="products.productvariant") )]
