from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Expense(models.Model):
    class Status(models.TextChoices): DRAFT="DRAFT","Brouillon"; PENDING="PENDING","En attente"; APPROVED="APPROVED","Approuvée"; REJECTED="REJECTED","Refusée"
    category = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.TextField()
    expense_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_expenses")
    approval_comment = models.TextField(blank=True)
    paid_in_cash = models.BooleanField(default=False)
    cash_session = models.ForeignKey("pos.CashSession", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
