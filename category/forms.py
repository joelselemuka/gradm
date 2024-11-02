from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from category.models import Categorie


class CategoryForm(forms.ModelForm):

     class Meta:
        model = Categorie
        fields = '__all__'

