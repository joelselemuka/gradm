from datetime import timedelta
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from apps.products.models import ProductVariant


class StockLotQuerySet(models.QuerySet):
    def sellable(self):
        return self.filter(quantity_available__gt=0).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.localdate()))

    def expiring(self, days=60):
        return self.filter(expires_at__gte=timezone.localdate(), expires_at__lte=timezone.localdate() + timedelta(days=days), quantity_available__gt=0)

    def low_stock(self):
        return self.values("variant_id").annotate(total=models.Sum("quantity_available"), threshold=models.Max("variant__low_stock_threshold")).filter(total__lte=F("threshold"))


class StockLot(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="lots")
    code = models.CharField(max_length=64)
    expires_at = models.DateField(null=True, blank=True, db_index=True)
    received_at = models.DateField(default=timezone.localdate)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_available = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    objects = StockLotQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["variant", "code"], name="unique_lot_per_variant")]
        indexes = [models.Index(fields=["variant", "expires_at"])]

    def __str__(self): return f"{self.variant} / {self.code}"


class StockMovement(models.Model):
    class Type(models.TextChoices):
        RECEIPT = "RECEIPT", "Réception"
        SALE = "SALE", "Vente"
        SALE_CANCELLED = "SALE_CANCELLED", "Annulation vente"
        RETURN = "RETURN", "Retour"
        ADJUSTMENT = "ADJUSTMENT", "Ajustement"
        STOCK_OUT = "STOCK_OUT", "Sortie de stock"
        LOSS = "LOSS", "Perte"
        EXPIRY = "EXPIRY", "Expiration"

    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=24, choices=Type.choices)
    quantity_delta = models.IntegerField()
    reference = models.CharField(max_length=100, db_index=True)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="stock_movements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(quantity_delta=0), name="stock_movement_delta_nonzero")]
        indexes = [models.Index(fields=["movement_type", "created_at"])]


class InventoryCount(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        CANCELLED = "CANCELLED", "Annulé"

    reference = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    note = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_counts_created")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_counts_completed")
    report_pdf = models.FileField(upload_to="inventory_reports/", null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class InventoryCountLine(models.Model):
    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="inventory_count_lines")
    system_quantity = models.PositiveIntegerField(default=0)
    counted_quantity = models.PositiveIntegerField(null=True, blank=True)
    difference = models.IntegerField(default=0)
    note = models.TextField(blank=True)
    counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["count", "variant"], name="unique_inventory_count_variant")]
        ordering = ["variant__product__name", "variant__name"]
