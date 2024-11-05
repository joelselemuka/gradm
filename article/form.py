from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from .models import Product


class ProductForm(forms.ModelForm):

     class Meta:
        model = Product
        fields = '__all__'