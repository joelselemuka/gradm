from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.forms import inlineformset_factory

from stock.models import Stock

from .models import Product, ProductCodeBarre, Variantes


class ProductForm(forms.ModelForm):

     class Meta:
        model = Product
        fields = '__all__'



class ProductForm2(forms.ModelForm):
    type=(('Produit simple','Produit simple'),('Produit varié','Produit varié'))
    productType= forms.ChoiceField(choices=type, widget=forms.RadioSelect, initial="Produit simple")
    class Meta:
        model = Product
        fields = '__all__'

class ImageForm(forms.ModelForm):

    class Meta:
        model = Stock
        fields = '__all__'
class VariantForm(forms.ModelForm):

    class Meta:
        model = Variantes
        fields = '__all__'
        widgets = {
            'codeRef': forms.TextInput(
                attrs={
                    'class': 'form-control'
                    }
                ),
            'varianteValue': forms.TextInput(
                attrs={
                    'class': 'form-control'
                    }
                ),
            'qteEnVente': forms.NumberInput(
                attrs={
                    'class': 'form-control'
                    }
                ),
            'pu': forms.NumberInput(
                attrs={
                    'class': 'form-control '
                    }
                ),
            'canExpiried': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input'
                    }
                ),
            'barreCode': forms.TextInput(
                attrs={
                    'class': 'form-control'
                }
            ),
            'expiried_on': forms.DateInput(
                attrs={
                    'class': ' c_datepicker form-control'
                }
            ),
            'status': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input'
                }
            ),
        }

VariantFormSet = inlineformset_factory(
    Product, Variantes, form=VariantForm,
    extra=1, can_delete=True, can_delete_extra=True
)

ImageFormSet = inlineformset_factory(
    Product, Stock, form=ImageForm,
    extra=1, can_delete=True, can_delete_extra=True
)
