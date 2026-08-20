from django import forms
from django.forms import ModelForm
from .models import Promotion
class PromotionForm(ModelForm):
    class Meta:
        model=Promotion; fields=("name","promotion_type","value","variant","category","min_quantity","priority","starts_at","ends_at","active")
        widgets={"starts_at":forms.DateTimeInput(attrs={"type":"datetime-local"}),"ends_at":forms.DateTimeInput(attrs={"type":"datetime-local"})}
