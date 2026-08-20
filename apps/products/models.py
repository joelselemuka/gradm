from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    active = models.BooleanField(default=True)

    def __str__(self): return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self): return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    internal_reference = models.CharField(max_length=64, unique=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True)
    expiration_managed = models.BooleanField(default=False)
    expiration_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["name", "active"])]

    def __str__(self): return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="variants")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=64, unique=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    manufacturer_barcode = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    store_barcode = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    unit = models.CharField(max_length=32, default="unité")
    volume_or_weight = models.CharField(max_length=64, blank=True)
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    sale_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField(default=5)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "name"], name="unique_variant_name_per_product")]
        indexes = [models.Index(fields=["product", "active"])]

    def __str__(self): return f"{self.product} · {self.sku}"
 
class ProductBarcode(models.Model):
    class Kind(models.TextChoices):
        MANUFACTURER = "MANUFACTURER", "Fabricant"
        INTERNAL = "INTERNAL", "Interne magasin"
        SUPPLIER = "SUPPLIER", "Fournisseur"
        LEGACY = "LEGACY", "Ancien code"

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="barcode_aliases")
    code = models.CharField(max_length=64, unique=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MANUFACTURER)
    source = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="created_product_barcodes")
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-active", "code"]
        indexes = [models.Index(fields=["variant", "active"])]

    def __str__(self):
        return f"{self.code} · {self.variant}"
