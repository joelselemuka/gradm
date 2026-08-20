import os
from django.core.management.base import BaseCommand
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Initialise un compte administrateur si aucun utilisateur n'existe ou selon les variables d'environnement."

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_USERNAME", "admin").strip()
        email = os.getenv("ADMIN_EMAIL", "admin@gsm.local").strip()
        password = os.getenv("ADMIN_PASSWORD", "Admin12345!").strip()
        force_reset = os.getenv("ADMIN_RESET_PASSWORD", "false").lower() == "true"

        user = User.objects.filter(username=username).first()

        if user:
            updated = False
            if user.role != User.Role.ADMIN or not user.is_staff or not user.is_superuser or not user.is_active:
                user.role = User.Role.ADMIN
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                updated = True
            if force_reset:
                user.set_password(password)
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Compte '{username}' mis a jour en tant qu'administrateur."))
            else:
                self.stdout.write(self.style.NOTICE(f"Compte '{username}' existe deja."))
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=User.Role.ADMIN,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Compte administrateur '{username}' cree avec succes."))
