from django import forms
from decimal import Decimal
from apps.products.models import ProductVariant


class StockReceiptForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.filter(active=True, product__active=True).select_related("product"), label="Article")
    lot_code = forms.CharField(max_length=64, label="Numero de lot")
    quantity = forms.IntegerField(min_value=1, label="Quantite recue")
    unit_cost = forms.DecimalField(min_value=0, decimal_places=2, max_digits=14, required=False, initial=Decimal("0.00"), widget=forms.HiddenInput())
    expires_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date expiration")
    reference = forms.CharField(max_length=100, label="Reference reception")


class StockIssueForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.filter(active=True, product__active=True).select_related("product"), label="Article")
    quantity = forms.IntegerField(min_value=1, label="Quantité sortie")
    reason = forms.CharField(max_length=300, label="Motif obligatoire")


class StockReceiptLineForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.filter(active=True, product__active=True).select_related("product"), label="Article")
    quantity = forms.IntegerField(min_value=1, label="Quantité")
    lot_code = forms.CharField(max_length=64, required=False, label="Lot (optionnel)")
    expires_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Expiration")


class StockIssueLineForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.filter(active=True, product__active=True).select_related("product"), label="Article")
    quantity = forms.IntegerField(min_value=1, label="Quantité")


class StockOperationForm(forms.Form):
    reference = forms.CharField(max_length=100, label="Référence de l’opération")
    reason = forms.CharField(max_length=300, required=False, label="Motif global")


class InventoryCountForm(forms.Form):
    reference = forms.CharField(max_length=64, required=False, label="Référence d'inventaire")
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")


class InventoryCountLineForm(forms.Form):
    counted_quantity = forms.IntegerField(min_value=0, label="Quantité comptée")
    note = forms.CharField(required=False, max_length=300)
