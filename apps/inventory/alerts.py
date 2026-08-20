from datetime import timedelta

from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.products.models import ProductVariant


def _variant_rows(kind, *, today=None):
    """Return one row per sellable variant, never one row per lot."""
    today = today or timezone.localdate()
    variants = ProductVariant.objects.filter(active=True, product__active=True).select_related("product").prefetch_related("lots")
    rows = []
    for variant in variants:
        stock = sum(lot.quantity_available for lot in variant.lots.all())
        if stock <= 0:
            continue
        dates = []
        if variant.product.expiration_managed and variant.product.expiration_date:
            dates.append(variant.product.expiration_date)
        dates.extend(lot.expires_at for lot in variant.lots.all() if lot.quantity_available > 0 and lot.expires_at)
        if kind == "expired":
            dates = [value for value in dates if value < today]
        elif kind == "expiring":
            dates = [value for value in dates if today <= value <= today + timedelta(days=60)]
        if not dates:
            continue
        expiration_date = min(dates)
        rows.append({"variant": variant, "product": variant.product, "expiration_date": expiration_date, "stock": stock})
    return sorted(rows, key=lambda row: (row["expiration_date"], row["product"].name, row["variant"].name))


def expired_rows(today=None):
    return _variant_rows("expired", today=today)


def expiring_rows(today=None):
    return _variant_rows("expiring", today=today)


def low_stock_rows():
    variants = ProductVariant.objects.filter(active=True, product__active=True).select_related("product").annotate(
        current_stock=Coalesce(Sum("lots__quantity_available"), Value(0))
    ).filter(current_stock__lte=F("low_stock_threshold")).order_by("current_stock", "product__name", "name")
    return list(variants)
