from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0003_invoice_customer")]
    operations = [migrations.AddField(model_name="invoice", name="customer_phone", field=models.CharField(blank=True, max_length=40))]
