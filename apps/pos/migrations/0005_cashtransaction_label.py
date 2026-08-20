from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pos", "0004_cash_currencies_and_closure")]

    operations = [
        migrations.AddField(
            model_name="cashtransaction",
            name="label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
