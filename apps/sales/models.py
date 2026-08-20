from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from uuid import uuid4
from apps.products.models import ProductVariant


class InvoiceQuerySet(models.QuerySet):
    def validated(self): return self.filter(status=Invoice.Status.VALIDATED)
    def today(self): return self.filter(created_at__date=timezone.localdate())


class Invoice(models.Model):
    class Status(models.TextChoices):
        VALIDATED = "VALIDATED", "Validée"
        CANCELLED = "CANCELLED", "Annulée"

    number = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.VALIDATED)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoices")
    cash_session = models.ForeignKey("pos.CashSession", null=True, blank=True, on_delete=models.PROTECT, related_name="invoices")
    customer_name = models.CharField(max_length=180, blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    customer = models.ForeignKey("customers.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="invoices")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    promotion_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    manual_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_invoices")
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = InvoiceQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self): return self.number


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=120)
    barcode = models.CharField(max_length=64, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    promotion_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    manual_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Espèces"
        CARD = "CARD", "Carte"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        OTHER = "OTHER", "Autre"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    cash_received = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    change_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Référence externe (ID terminal carte, numéro transaction mobile money, etc.)
    # Obligatoire pour permettre le rapprochement bancaire hors espèces.
    transaction_reference = models.CharField(max_length=120, blank=True, default="")
    # Clé d'idempotence : protège contre les doubles paiements en cas de retry réseau.
    idempotency_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "method"],
                name="unique_payment_per_invoice_method",
            )
        ]
