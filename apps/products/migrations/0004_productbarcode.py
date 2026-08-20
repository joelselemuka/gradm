import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_product_expiration_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductBarcode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=64, unique=True)),
                ("kind", models.CharField(choices=[("MANUFACTURER", "Fabricant"), ("INTERNAL", "Interne magasin"), ("SUPPLIER", "Fournisseur"), ("LEGACY", "Ancien code")], default="MANUFACTURER", max_length=16)),
                ("source", models.CharField(blank=True, max_length=120)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_product_barcodes", to=settings.AUTH_USER_MODEL)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="barcode_aliases", to="products.productvariant")),
            ],
            options={"ordering": ["-active", "code"]},
        ),
        migrations.AddIndex(model_name="productbarcode", index=models.Index(fields=["variant", "active"], name="products_pr_variant_d8375e_idx")),
    ]
