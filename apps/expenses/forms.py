from django import forms
from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model=Expense; fields=("category","amount","description")


class DecisionForm(forms.Form): comment=forms.CharField(required=False, widget=forms.Textarea(attrs={"rows":2}), label="Commentaire")
