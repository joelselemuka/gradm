from django import forms

from .models import StoreSettings


class StoreSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enabled = self.instance.discounts_enabled
        if self.is_bound:
            enabled = self.data.get("discounts_enabled") in {"on", "1", "true", "True"}
        for field_name in ("promotion_threshold", "promotion_type", "promotion_value", "manual_discount_limit"):
            self.fields[field_name].widget.attrs["x-bind:disabled"] = "!discountsEnabled"
            self.fields[field_name].required = enabled

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("discounts_enabled"):
            cleaned["promotion_enabled"] = False
            defaults = {
                "promotion_threshold": self.instance.promotion_threshold or 0,
                "promotion_type": self.instance.promotion_type or StoreSettings.DiscountType.PERCENT,
                "promotion_value": self.instance.promotion_value or 0,
                "manual_discount_limit": self.instance.manual_discount_limit or 0,
            }
            for field_name, default in defaults.items():
                if cleaned.get(field_name) in (None, ""):
                    cleaned[field_name] = default
        return cleaned

    class Meta:
        model = StoreSettings
        fields = (
            "name",
            "address",
            "contact",
            "ccm_number",
            "national_id",
            "report_recipient_email",
            "currency",
            "invoice_prefix",
            "low_stock_threshold",
            "expiry_alert_days",
            "discounts_enabled",
            "promotion_enabled",
            "promotion_threshold",
            "promotion_type",
            "promotion_value",
            "manual_discount_limit",
            "exchange_rate",
        )
        labels = {
            "name": "Nom du commerce",
            "address": "Adresse",
            "contact": "Contact",
            "ccm_number": "N° CCM",
            "national_id": "Identifiant national",
            "report_recipient_email": "Email destinataire des rapports",
            "currency": "Devise principale",
            "invoice_prefix": "Préfixe des factures",
            "low_stock_threshold": "Seuil d'alerte stock",
            "expiry_alert_days": "Alerte expiration (jours)",
            "discounts_enabled": "Activer les réductions",
            "promotion_enabled": "Activer la promotion par seuil",
            "promotion_threshold": "Seuil minimum de facture",
            "promotion_type": "Type de promotion",
            "promotion_value": "Valeur de promotion",
            "manual_discount_limit": "Plafond de remise accordée",
            "exchange_rate": "Taux de change",
        }
        help_texts = {
            "promotion_threshold": "La promotion s'applique lorsque le total de la vente atteint ce montant.",
            "promotion_value": "Pourcentage ou montant fixe selon le type sélectionné.",
            "manual_discount_limit": "Montant maximal qu'un caissier peut saisir comme remise accordée.",
            "exchange_rate": "Valeur d'une unité de devise étrangère dans la devise principale.",
            "report_recipient_email": "Le rapport général sera envoyé à cette adresse après la clôture de la journée.",
        }
        widgets = {
            "promotion_threshold": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "promotion_type": forms.Select(),
            "promotion_value": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "manual_discount_limit": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "exchange_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "discounts_enabled": forms.CheckboxInput(attrs={"x-model": "discountsEnabled"}),
            "promotion_enabled": forms.CheckboxInput(attrs={"x-model": "promotionEnabled", "x-bind:disabled": "!discountsEnabled"}),
        }
