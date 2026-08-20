from django import forms
from django.contrib.auth import get_user_model
from .models import CashRegister, CashTransaction


class CashRegisterForm(forms.ModelForm):
    class Meta:
        model = CashRegister
        fields = ("name",)
        labels = {"name": "Nom de la caisse"}


class CashSessionOpenForm(forms.Form):
    register = forms.ModelChoiceField(queryset=CashRegister.objects.filter(active=True), label="Caisse")
    cashier = forms.ModelChoiceField(queryset=get_user_model().objects.none(), label="Caissier")
    opening_local_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, required=False, initial=0, label="Fonds initial (FC)")
    opening_foreign_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, required=False, initial=0, label="Fonds initial (USD)")
    use_previous_balance = forms.BooleanField(
        required=False,
        label="Utiliser le solde de versement précédent comme cash initial",
        help_text="Si coché, les fonds initiaux seront remplacés par le solde de la dernière session clôturée sur cette caisse.",
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(is_active=True, role__in=["ADMIN", "MANAGER", "CASHIER"])
        self.fields["cashier"].queryset = users if actor and actor.can_manage_cash() else users.filter(pk=getattr(actor, "pk", None))



class CashMovementForm(forms.Form):
    label = forms.CharField(max_length=120, label="Libellé", help_text="Ex. Achat fournitures, avance du responsable…")
    direction = forms.ChoiceField(choices=CashTransaction.Direction.choices, label="Sens")
    local_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, required=False, label="Montant FC")
    foreign_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, required=False, label="Montant USD")
    description = forms.CharField(max_length=300, label="Motif")

    def __init__(self, *args, direction=None, **kwargs):
        super().__init__(*args, **kwargs)
        if direction:
            self.fields["direction"].initial = direction
            self.fields["direction"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("local_amount") and not cleaned.get("foreign_amount"):
            raise forms.ValidationError("Saisissez un montant en FC, en USD, ou les deux.")
        if not cleaned.get("label"):
            self.add_error("label", "Le libellé est obligatoire.")
        if not cleaned.get("description"):
            self.add_error("description", "Le motif est obligatoire.")
        direction = cleaned.get("direction")
        if direction == CashTransaction.Direction.IN:
            cleaned["category"] = CashTransaction.Category.OWNER_DEPOSIT
        elif direction == CashTransaction.Direction.OUT:
            cleaned["category"] = CashTransaction.Category.WITHDRAWAL
        else:
            self.add_error("direction", "Le sens du mouvement est invalide.")
        return cleaned


class CashExchangeForm(forms.Form):
    foreign_amount = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        max_digits=14,
        label="Montant reçu en USD",
        help_text="Le montant sera converti automatiquement en FC au taux configuré.",
    )


class CashSessionCloseForm(forms.Form):
    sales_deposit_local_amount = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=14, label="Versement ventes en FC", widget=forms.NumberInput(attrs={"required": "required"}))
    sales_deposit_foreign_amount = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=14, label="Versement ventes en USD", widget=forms.NumberInput(attrs={"required": "required"}))
    counted_local_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, label="Versement cash en FC")
    counted_foreign_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, label="Versement cash en USD")


class VoidCashMovementForm(forms.Form):
    reason = forms.CharField(max_length=300, label="Motif d'annulation")
