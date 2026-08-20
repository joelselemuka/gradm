from django import forms
from apps.core.models import StoreSettings


class CheckoutForm(forms.Form):
    # Le POS n'accepte désormais que les espèces : le montant reçu est donc
    # indispensable pour valider une facture et calculer la monnaie.
    cash_received = forms.DecimalField(required=True, min_value=0, decimal_places=2, max_digits=14, label="Montant reçu")
    manual_discount = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=14, initial=0, label="Réduction")
    customer_name = forms.CharField(required=False, max_length=180, label="Nom du client")
    customer_phone = forms.CharField(required=False, max_length=40, label="Téléphone du client")

    def __init__(self, *args, store_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store_settings = store_settings or StoreSettings.get_solo()
        discount_field = self.fields["manual_discount"]
        discount_field.max_value = self.store_settings.manual_discount_limit
        discount_field.disabled = not self.store_settings.discounts_enabled or self.store_settings.manual_discount_limit <= 0
        discount_field.help_text = "Remise accordée autorisée par l'administrateur."

    def clean_manual_discount(self):
        return self.cleaned_data["manual_discount"] or 0


class CancellationForm(forms.Form):
    reason = forms.CharField(max_length=500, label="Motif obligatoire")
