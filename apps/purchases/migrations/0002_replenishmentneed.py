from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("purchases", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ReplenishmentNeed",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("threshold_snapshot", models.PositiveIntegerField()),
                ("available_snapshot", models.PositiveIntegerField()),
                ("suggested_quantity", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("OPEN", "À commander"), ("ORDERED", "Commandé"), ("RESOLVED", "Résolu")], db_index=True, default="OPEN", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="replenishment_needs", to="products.productvariant")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="replenishmentneed", constraint=models.UniqueConstraint(condition=models.Q(("status", "OPEN")), fields=("variant",), name="one_open_replenishment_need_per_variant")),
    ]
