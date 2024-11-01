
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from personnel.models import Personnel


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)






class User(AbstractUser):
    user_type =(
        ('ADMIN', 'ADMIN '),
        ('GERANT', 'GERANT'),
        ('CAISSIER', 'CAISSIER'),
    )
    agent = models.ForeignKey(Personnel, on_delete=models.CASCADE)
    username = models.CharField(_("Nom d'utilisateur"), max_length=200)
    email = models.EmailField(_("email address"), unique=True)
    user_type = models.CharField(_("Type d'utilisateur"), choices=user_type, max_length=150, default="CAISSIER")
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['email', 'user_type']

    objects = CustomUserManager()

    def __str__(self):
        return self.email
