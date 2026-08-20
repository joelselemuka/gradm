from django import forms
from apps.pos.models import CashSession
from apps.products.models import ProductVariant
from .models import PurchaseOrder, PurchaseOrderLine

class PurchaseOrderForm(forms.ModelForm):
    class Meta: model=PurchaseOrder; fields=("supplier","reference","paid_in_cash","cash_session")
    def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs); self.fields["cash_session"].queryset=CashSession.objects.filter(status=CashSession.Status.OPEN)

class PurchaseLineForm(forms.ModelForm):
    class Meta: model=PurchaseOrderLine; fields=("variant","ordered_quantity","unit_cost")

class ReceivePurchaseLineForm(forms.Form):
    line=forms.ModelChoiceField(queryset=PurchaseOrderLine.objects.none(), label="Ligne")
    quantity=forms.IntegerField(min_value=1, label="Quantité reçue")
    lot_code=forms.CharField(max_length=64, label="Lot")
    expires_at=forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}), label="Expiration")
    def __init__(self,*args,order=None,**kwargs): super().__init__(*args,**kwargs); self.fields["line"].queryset=order.lines.select_related("variant__product") if order else PurchaseOrderLine.objects.none()
