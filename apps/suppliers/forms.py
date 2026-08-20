from django.forms import ModelForm
from .models import Supplier
class SupplierForm(ModelForm):
    class Meta: model = Supplier; fields = ("name", "contact_name", "phone", "email", "address", "tax_number", "active")
