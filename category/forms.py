from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from article.models import Categorie


class CategoryForm(forms.ModelForm):
     CHOICES= (('Activée', 'Activée '),('Désactivée', 'Désactivée'))
    
     Status = forms.ChoiceField(widget=forms.Select, choices=CHOICES)
     Name = forms.CharField(widget=forms.TextInput(attrs={'type' :'text', 'class': 'form-control',}))


     class Meta:
        model = Categorie
        fields = ['Name', 'Status']


     def clean_name(self,*args,**kwargs):
        name = self.cleaned_data.get('Name')
        cat=Categorie.objects.filter(Name=name).exists()
        if cat:
            raise forms.ValidationError("Cette catégorie existe déjà!")
        else:
            return name
