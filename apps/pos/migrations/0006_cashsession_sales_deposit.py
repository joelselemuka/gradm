from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pos", "0005_cashtransaction_label")]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="expected_sales",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="sales_deposit_local_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="sales_deposit_foreign_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="sales_difference",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
    ]
