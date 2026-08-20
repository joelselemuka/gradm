import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_stockmovement_stock_out"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="InventoryCount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("DRAFT", "Brouillon"), ("IN_PROGRESS", "En cours"), ("COMPLETED", "Terminé"), ("CANCELLED", "Annulé")], db_index=True, default="DRAFT", max_length=16)),
                ("note", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_counts_completed", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_counts_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="InventoryCountLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("system_quantity", models.PositiveIntegerField(default=0)),
                ("counted_quantity", models.PositiveIntegerField(blank=True, null=True)),
                ("difference", models.IntegerField(default=0)),
                ("note", models.TextField(blank=True)),
                ("counted_at", models.DateTimeField(blank=True, null=True)),
                ("count", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="inventory.inventorycount")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_count_lines", to="products.productvariant")),
            ],
            options={"ordering": ["variant__product__name", "variant__name"]},
        ),
        migrations.AddConstraint(model_name="inventorycountline", constraint=models.UniqueConstraint(fields=("count", "variant"), name="unique_inventory_count_variant")),
    ]
