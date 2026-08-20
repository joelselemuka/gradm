import django.core.validators
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("pos", "0003_alter_cashtransaction_exchange_rate")]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="opening_local_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="opening_foreign_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(model_name="cashsession", name="expected_local_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(model_name="cashsession", name="expected_foreign_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(model_name="cashsession", name="counted_local_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(model_name="cashsession", name="counted_foreign_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(model_name="cashsession", name="difference_local_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AddField(model_name="cashsession", name="difference_foreign_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
        migrations.AlterField(
            model_name="cashtransaction",
            name="amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.RemoveConstraint(model_name="cashtransaction", name="cash_transaction_positive_amount"),
        migrations.AddConstraint(
            model_name="cashtransaction",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0) | Q(foreign_amount__gt=0), name="cash_transaction_positive_amount"),
        ),
    ]
