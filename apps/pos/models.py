from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
import uuid


class CashRegister(models.Model):
    name = models.CharField(max_length=80, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self): return self.name


class CashSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouverte"
        CLOSED = "CLOSED", "Fermée"

    register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="sessions")
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_sessions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opening_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    opening_local_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    opening_foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    expected_sales = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sales_deposit_local_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sales_deposit_foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sales_difference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    expected_local_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    expected_foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    counted_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    counted_local_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    counted_foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    difference_local_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    difference_foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # PDF de clôture généré automatiquement à la fermeture de session.
    report_pdf = models.FileField(upload_to="reports/sessions/", null=True, blank=True, verbose_name="Rapport PDF de clôture")
    # Solde de versement : (Solde général − Total versement).
    # Permet à l'admin de reporter ce montant comme fonds initial de la session suivante.
    deposit_balance_local = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Solde versement (FC)")
    deposit_balance_foreign = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="Solde versement (USD)")


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["register"], condition=Q(status="OPEN"), name="one_open_session_per_register"),
            models.UniqueConstraint(fields=["cashier"], condition=Q(status="OPEN"), name="one_open_session_per_cashier"),
        ]

    def __str__(self):
        return f"{self.register} — {self.opened_at:%d/%m/%Y}"

    @property
    def sales_difference_abs(self):
        return abs(self.sales_difference or 0)

    @property
    def cash_difference_abs(self):
        return abs(self.difference or 0)


class CashTransaction(models.Model):
    """Immutable, manual cash movement. Cash sales remain sourced from payments."""
    class Direction(models.TextChoices):
        IN = "IN", "Entrée"
        OUT = "OUT", "Sortie"

    class Category(models.TextChoices):
        OPENING_FLOAT = "OPENING_FLOAT", "Fonds initial"
        OWNER_DEPOSIT = "OWNER_DEPOSIT", "Apport du responsable"
        PURCHASE = "PURCHASE", "Achat payé en espèces"
        EXPENSE = "EXPENSE", "Dépense"
        WITHDRAWAL = "WITHDRAWAL", "Retrait"
        EXCHANGE_IN = "EXCHANGE_IN", "Change — espèces reçues"
        EXCHANGE_OUT = "EXCHANGE_OUT", "Change — espèces remises"
        ADJUSTMENT = "ADJUSTMENT", "Ajustement autorisé"

    session = models.ForeignKey(CashSession, on_delete=models.PROTECT, related_name="cash_transactions")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    category = models.CharField(max_length=20, choices=Category.choices)
    label = models.CharField(max_length=120, blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    description = models.CharField(max_length=300)
    reference = models.CharField(max_length=100, blank=True)
    foreign_currency = models.CharField(max_length=8, blank=True)
    foreign_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.01)])
    exchange_rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.01)])
    group_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_transactions")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="voided_cash_transactions")
    void_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        indexes = [models.Index(fields=["session", "direction", "created_at"])]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0) | Q(foreign_amount__gt=0), name="cash_transaction_positive_amount")]
        ordering = ["-created_at", "-pk"]

    @property
    def signed_amount(self):
        return self.amount if self.direction == self.Direction.IN else -self.amount

    @property
    def local_amount(self):
        """FC amount; ``amount`` remains the legacy database column."""
        return self.amount

    @property
    def signed_foreign_amount(self):
        value = self.foreign_amount or 0
        return value if self.direction == self.Direction.IN else -value

    @property
    def is_voided(self):
        return self.voided_at is not None
