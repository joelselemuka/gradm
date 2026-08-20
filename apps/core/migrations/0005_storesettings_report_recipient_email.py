from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_storesettings_address_storesettings_ccm_number_and_more")]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="report_recipient_email",
            field=models.EmailField(
                blank=True,
                help_text="Adresse qui reçoit le rapport général de clôture et le rapport quotidien.",
                max_length=254,
            ),
        ),
    ]
