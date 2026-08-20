from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class UserCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "is_active")


class UserUpdateForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput, label="Nouveau mot de passe")
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "is_active")
    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data["password"]: user.set_password(self.cleaned_data["password"])
        if commit: user.save()
        return user
