from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from apps.core.models import StoreSettings
from .models import Promotion

class DiscountService:
    @staticmethod
    def promotion_discount(*, variant, quantity, unit_price):
        now=timezone.now(); choices=Promotion.objects.filter(active=True,starts_at__lte=now,ends_at__gte=now,min_quantity__lte=quantity).filter(Q(variant=variant)|Q(category=variant.product.category)).order_by("-priority","pk")
        promo=choices.first()
        if not promo: return Decimal("0"),None
        base=unit_price*quantity
        discount=(base*promo.value/Decimal("100")) if promo.promotion_type==Promotion.Type.PERCENT else promo.value
        return min(base,discount),promo

    @staticmethod
    def configured_order_discount(*, subtotal):
        """Return the configured invoice-level promotion for the current store."""
        settings = StoreSettings.get_solo()
        if not settings.discounts_enabled or not settings.promotion_enabled:
            return Decimal("0"), settings
        if subtotal < settings.promotion_threshold:
            return Decimal("0"), settings
        if settings.promotion_type == StoreSettings.DiscountType.PERCENT:
            discount = subtotal * settings.promotion_value / Decimal("100")
        else:
            discount = settings.promotion_value
        return min(subtotal, discount).quantize(Decimal("0.01")), settings

    @staticmethod
    def validate_manual_discount(*, amount, subtotal):
        settings = StoreSettings.get_solo()
        amount = Decimal(amount or 0).quantize(Decimal("0.01"))
        if amount < 0:
            raise ValidationError("La remise accordée ne peut pas être négative.")
        if amount and not settings.discounts_enabled:
            raise ValidationError("Les réductions sont désactivées par l'administrateur.")
        if amount > settings.manual_discount_limit:
            raise ValidationError("La remise accordée dépasse le plafond autorisé.")
        if amount > subtotal:
            raise ValidationError("La remise accordée ne peut pas dépasser le total de la vente.")
        return amount
