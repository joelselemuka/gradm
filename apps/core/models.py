from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class StoreSettings(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Pourcentage"
        FIXED = "FIXED", "Montant fixe"

    name = models.CharField(max_length=150, default="Mon supermarché")
    address = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=120, blank=True)
    ccm_number = models.CharField(max_length=80, blank=True)
    national_id = models.CharField(max_length=80, blank=True)
    report_recipient_email = models.EmailField(
        blank=True,
        help_text="Adresse qui reçoit le rapport général de clôture et le rapport quotidien.",
    )
    currency = models.CharField(max_length=8, default="FC")
    invoice_prefix = models.CharField(max_length=20, default="FAC")
    low_stock_threshold = models.PositiveIntegerField(default=5)
    expiry_alert_days = models.PositiveIntegerField(default=30)
    discounts_enabled = models.BooleanField(default=False)
    promotion_enabled = models.BooleanField(default=False)
    promotion_threshold = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    promotion_type = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.PERCENT)
    promotion_value = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    manual_discount_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    exchange_rate = models.DecimalField(max_digits=14, decimal_places=2, default=1, validators=[MinValueValidator(Decimal("0.01"))])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "store settings"

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.promotion_enabled and not self.discounts_enabled:
            errors["promotion_enabled"] = "Activez d'abord l'option générale des réductions."
        if self.promotion_enabled and self.discounts_enabled:
            if self.promotion_threshold <= 0:
                errors["promotion_threshold"] = "Le seuil promotionnel doit être supérieur à zéro."
            if self.promotion_value <= 0:
                errors["promotion_value"] = "La valeur promotionnelle doit être supérieure à zéro."
            if self.promotion_type == self.DiscountType.PERCENT and self.promotion_value > 100:
                errors["promotion_value"] = "Un taux promotionnel ne peut pas dépasser 100 %."
        if errors:
            raise ValidationError(errors)
