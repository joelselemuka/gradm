from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        MANAGER = "MANAGER", "Gérant"
        CASHIER = "CASHIER", "Caissier"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CASHIER)
    is_active = models.BooleanField(default=True)

    def can_cancel_invoice(self):
        return self.role == self.Role.ADMIN

    def can_approve_expense(self):
        return self.role == self.Role.ADMIN

    def can_operate_pos(self):
        # L'administrateur supervise les ventes ; il n'encaisse jamais depuis le POS.
        return self.role in {self.Role.MANAGER, self.Role.CASHIER}

    def can_manage_cash(self):
        """The owner/administrator is accountable for cash movements."""
        return self.role == self.Role.ADMIN

    def can_manage_catalogue(self):
        return self.role in {self.Role.ADMIN, self.Role.MANAGER}

    def can_manage_inventory(self):
        return self.role in {self.Role.ADMIN, self.Role.MANAGER}
