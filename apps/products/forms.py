from decimal import Decimal
from django import forms
from django.db import transaction
from django.db.models import Q
from .models import Brand, Category, Product, ProductBarcode, ProductVariant


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "internal_reference", "category", "brand", "description", "expiration_managed", "expiration_date", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True


class ProductEditForm(forms.ModelForm):
    brand_name = forms.CharField(max_length=100, required=False, label="Marque")

    class Meta:
        model = Product
        fields = ("name", "internal_reference", "category", "description", "expiration_managed", "expiration_date", "active")
        widgets = {"expiration_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True
        if self.instance and self.instance.brand_id:
            self.fields["brand_name"].initial = self.instance.brand.name

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("expiration_managed") and not cleaned.get("expiration_date"):
            self.add_error("expiration_date", "La date d’expiration est obligatoire pour un produit périssable.")
        if not cleaned.get("expiration_managed"):
            cleaned["expiration_date"] = None
        return cleaned
        codes = [("manufacturer_barcode", cleaned.get("manufacturer_barcode")), ("store_barcode", cleaned.get("store_barcode"))]
        for field_name, value in codes:
            value = (value or "").strip()
            if not value:
                continue
            used = ProductVariant.objects.filter(Q(barcode=value) | Q(manufacturer_barcode=value) | Q(store_barcode=value)).exists() or ProductBarcode.objects.filter(code=value).exists()
            if used:
                self.add_error(field_name, "Ce code existe déjà. Vérifiez l'article existant ou choisissez un autre code.")
        return cleaned

    def save(self, commit=True):
        product = super().save(commit=False)
        brand_name = self.cleaned_data["brand_name"].strip()
        product.brand = Brand.objects.get_or_create(name=brand_name)[0] if brand_name else None
        if commit:
            product.save()
        return product


class VariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("name", "sku", "manufacturer_barcode", "store_barcode", "barcode", "unit", "volume_or_weight", "purchase_price", "sale_price", "low_stock_threshold", "active")
        labels = {"manufacturer_barcode": "Code-barres fabricant", "store_barcode": "Code-barres interne supermarché", "barcode": "Code-barres de vente (compatibilité)", "low_stock_threshold": "Stock d'alerte"}


class ProductBarcodeForm(forms.ModelForm):
    class Meta:
        model = ProductBarcode
        fields = ("code",)
        labels = {"code": "Code-barres du produit"}

    def clean_code(self):
        return self.cleaned_data["code"].strip()


class NewArticleForm(forms.Form):
    name = forms.CharField(max_length=200, label="Nom du produit")
    internal_reference = forms.CharField(max_length=64, label="Référence interne")
    category = forms.ModelChoiceField(queryset=Category.objects.filter(active=True), label="Catégorie")
    brand = forms.CharField(max_length=100, required=False, label="Marque")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Description")
    expiration_managed = forms.BooleanField(required=False, label="Produit avec date d’expiration")
    expiration_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’expiration")
    sku = forms.CharField(max_length=64, label="SKU")
    manufacturer_barcode = forms.CharField(max_length=64, required=False, label="Code-barres fabricant")
    store_barcode = forms.CharField(max_length=64, required=False, label="Code-barres interne supermarché")
    sale_price = forms.DecimalField(min_value=0, max_digits=14, decimal_places=2, label="Prix de vente")
    low_stock_threshold = forms.IntegerField(min_value=0, initial=5, label="Stock d’alerte")

    def _clean_barcode(self, value):
        value = (value or "").strip()
        if value and (ProductVariant.objects.filter(Q(barcode=value) | Q(manufacturer_barcode=value) | Q(store_barcode=value)).exists() or ProductBarcode.objects.filter(code=value).exists()):
            raise forms.ValidationError("Ce code existe déjà. Vérifiez l'article existant ou choisissez un autre code.")
        return value

    def clean_manufacturer_barcode(self):
        return self._clean_barcode(self.cleaned_data.get("manufacturer_barcode"))

    def clean_store_barcode(self):
        return self._clean_barcode(self.cleaned_data.get("store_barcode"))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("expiration_managed") and not cleaned.get("expiration_date"):
            self.add_error("expiration_date", "La date d’expiration est obligatoire pour un produit périssable.")
        if not cleaned.get("expiration_managed"):
            cleaned["expiration_date"] = None
        return cleaned

    @transaction.atomic
    def save(self, actor=None):
        from .services import ProductBarcodeService
        brand_name = self.cleaned_data["brand"].strip()
        brand = Brand.objects.get_or_create(name=brand_name)[0] if brand_name else None
        product = Product.objects.create(name=self.cleaned_data["name"], internal_reference=self.cleaned_data["internal_reference"], category=self.cleaned_data["category"], brand=brand, description=self.cleaned_data["description"], expiration_managed=self.cleaned_data["expiration_managed"], expiration_date=self.cleaned_data["expiration_date"])
        variant = ProductVariant.objects.create(product=product, name="Article", sku=self.cleaned_data["sku"], manufacturer_barcode=self.cleaned_data["manufacturer_barcode"] or None, store_barcode=self.cleaned_data["store_barcode"] or None, purchase_price=Decimal("0.00"), sale_price=self.cleaned_data["sale_price"], low_stock_threshold=self.cleaned_data["low_stock_threshold"])
        if self.cleaned_data["manufacturer_barcode"]:
            ProductBarcodeService.add_alias(variant, self.cleaned_data["manufacturer_barcode"], ProductBarcode.Kind.MANUFACTURER, actor=actor)
        if self.cleaned_data["store_barcode"]:
            ProductBarcodeService.add_alias(variant, self.cleaned_data["store_barcode"], ProductBarcode.Kind.INTERNAL, actor=actor)
        ProductBarcodeService.ensure_internal_code(variant, actor=actor)
        return variant


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "parent", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = Category.objects.exclude(pk=self.instance.pk).order_by("name")


class QuickCategoryForm(forms.Form):
    name = forms.CharField(max_length=100, label="Nouvelle catégorie")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Category.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("Cette catégorie existe déjà.")
        return name
