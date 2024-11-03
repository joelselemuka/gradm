from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from article.models import UniteVente
from category.models import Categorie


class UnityForm(forms.ModelForm):

     class Meta:
        model = UniteVente
        fields = '__all__'

