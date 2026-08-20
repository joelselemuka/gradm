from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Ajoute 3 champs à CashSession :
      - report_pdf            : PDF de clôture (FileField, optionnel)
      - deposit_balance_local : solde de versement en FC (pour report en session suivante)
      - deposit_balance_foreign : solde de versement en USD
    """

    dependencies = [
        ("pos", "0006_cashsession_sales_deposit"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="report_pdf",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="reports/sessions/",
                verbose_name="Rapport PDF de clôture",
            ),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="deposit_balance_local",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                verbose_name="Solde de versement (FC)",
                help_text="Solde (Solde général − Total versement) en FC, reportable comme cash initial.",
            ),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="deposit_balance_foreign",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                verbose_name="Solde de versement (USD)",
            ),
        ),
    ]
