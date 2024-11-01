from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from category.models import Categorie


class CategoryForm(forms.ModelForm):

     class Meta:
        model = Categorie
        fields = '__all__'


     def clean_name(self,*args,**kwargs):
        name = self.cleaned_data.get('name')
        cat=Categorie.objects.filter(name=name).exists()
        if cat:
            raise forms.ValidationError("Cette catégorie existe déjà!")
        else:
            return name
