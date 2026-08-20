from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import F, Min, Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CategoryForm, NewArticleForm, ProductBarcodeForm, ProductEditForm, ProductForm, QuickCategoryForm, VariantForm
from .models import Category, Product, ProductBarcode, ProductVariant
from .services import ProductBarcodeService, barcode_svg


def _catalogue_manager(request):
    if not request.user.can_manage_catalogue():
        raise PermissionDenied("Accès catalogue non autorisé.")


def _category_admin(request):
    if not request.user.can_manage_cash():
        raise PermissionDenied("Seul un administrateur peut gérer les catégories.")


@login_required
def product_list(request):
    _catalogue_manager(request)
    query = request.GET.get("q", "").strip()
    stock_filter = request.GET.get("stock", "")
    expiration_filter = request.GET.get("expiration", "")
    category_filter = request.GET.get("category", "")
    products = Product.objects.select_related("category", "brand").prefetch_related("variants").order_by("name")
    if query:
        products = products.filter(Q(name__icontains=query) | Q(internal_reference__icontains=query) | Q(variants__sku__icontains=query) | Q(variants__barcode__icontains=query) | Q(variants__barcode_aliases__code__icontains=query, variants__barcode_aliases__active=True)).distinct()
    products = products.annotate(current_stock=Sum("variants__lots__quantity_available"), sale_price=Min("variants__sale_price"))
    if category_filter.isdigit(): products = products.filter(category_id=category_filter)
    if stock_filter == "low": products = products.filter(variants__lots__quantity_available__lte=F("variants__low_stock_threshold"))
    elif stock_filter == "out": products = products.filter(current_stock__isnull=True)
    if expiration_filter == "expired": products = products.filter(variants__lots__expires_at__lt=timezone.localdate(), variants__lots__quantity_available__gt=0)
    elif expiration_filter == "soon": products = products.filter(variants__lots__expires_at__gte=timezone.localdate(), variants__lots__expires_at__lte=timezone.localdate() + timedelta(days=30), variants__lots__quantity_available__gt=0)
    active_variants = ProductVariant.objects.filter(active=True, product__active=True).select_related("product").order_by("product__name", "name")
    return render(request, "products/list.html", {"products": Paginator(products.distinct(), 20).get_page(request.GET.get("page")), "active_variants": active_variants, "query": query, "categories": Category.objects.filter(active=True).order_by("name"), "stock_filter": stock_filter, "expiration_filter": expiration_filter, "category_filter": category_filter})


@login_required
def product_create(request):
    _catalogue_manager(request)
    form = NewArticleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        variant = form.save(actor=request.user)
        messages.success(request, "Article créé avec son prix, ses codes-barres et son seuil d’alerte.")
        return redirect("products:list")
    return render(request, "products/form.html", {"form": form, "title": "Nouveau produit"})


@login_required
def product_detail(request, pk):
    _catalogue_manager(request)
    product = get_object_or_404(Product.objects.select_related("category", "brand").prefetch_related("variants__lots", "variants__barcode_aliases"), pk=pk)
    from apps.inventory.models import StockMovement
    from apps.sales.models import Invoice, InvoiceLine
    movements = StockMovement.objects.filter(lot__variant__product=product).select_related("lot__variant", "actor").order_by("-created_at")[:12]
    recent_sales = InvoiceLine.objects.filter(variant__product=product, invoice__status=Invoice.Status.VALIDATED).select_related("invoice", "invoice__cashier", "variant").order_by("-invoice__created_at")[:5]
    stock_total = product.variants.aggregate(total=Sum("lots__quantity_available"))["total"] or 0
    for variant in product.variants.all():
        variant.printable_barcodes = [{"code": alias.code, "svg": barcode_svg(alias.code)} for alias in variant.barcode_aliases.all() if alias.active and barcode_svg(alias.code)]
    return render(request, "products/detail.html", {"product": product, "variant_form": VariantForm(), "barcode_form": ProductBarcodeForm(), "stock_total": stock_total, "movements": movements, "recent_sales": recent_sales})


@login_required
def product_update(request, pk):
    _catalogue_manager(request)
    product = get_object_or_404(Product, pk=pk)
    form = ProductEditForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Article mis à jour.")
        return redirect("products:list")
    return render(request, "products/product_edit.html", {"form": form, "product": product})


@login_required
def product_toggle_active(request, pk):
    _catalogue_manager(request)
    if request.method != "POST":
        return redirect("products:list")
    product = get_object_or_404(Product, pk=pk)
    product.active = not product.active
    product.save(update_fields=["active", "updated_at"])
    messages.success(request, f"Article {'activé' if product.active else 'désactivé'}.")
    return redirect("products:list")


@login_required
def product_delete(request, pk):
    _catalogue_manager(request)
    if request.method != "POST":
        return redirect("products:list")
    product = get_object_or_404(Product, pk=pk)
    try:
        with transaction.atomic():
            # ProductVariant protects its parent. An unused article can therefore
            # be removed together with its variants; historical variants stay immutable.
            for variant in product.variants.all():
                variant.delete()
            product.delete()
        messages.success(request, "Article supprimé.")
    except ProtectedError:
        messages.error(request, "Cet article possède un historique de stock ou de ventes : désactivez-le plutôt que de le supprimer.")
    return redirect("products:list")


@login_required
def variant_create(request, pk):
    _catalogue_manager(request)
    product = get_object_or_404(Product, pk=pk)
    form = VariantForm(request.POST)
    if form.is_valid():
        variant = form.save(commit=False); variant.product = product; variant.save()
        if variant.manufacturer_barcode:
            ProductBarcodeService.add_alias(variant, variant.manufacturer_barcode, ProductBarcode.Kind.MANUFACTURER, actor=request.user)
        if variant.store_barcode:
            ProductBarcodeService.add_alias(variant, variant.store_barcode, ProductBarcode.Kind.INTERNAL, actor=request.user)
        ProductBarcodeService.ensure_internal_code(variant, actor=request.user)
        messages.success(request, "Article ajouté.")
    else: messages.error(request, "L’article n’a pas pu être créé. Vérifiez les champs.")
    return redirect("products:detail", pk=product.pk)


@login_required
def barcode_add(request, product_pk, variant_pk):
    _catalogue_manager(request)
    variant = get_object_or_404(ProductVariant, pk=variant_pk, product_id=product_pk)
    if request.method != "POST":
        return redirect("products:detail", pk=product_pk)
    form = ProductBarcodeForm(request.POST)
    if form.is_valid():
        try:
            ProductBarcodeService.add_alias(variant, form.cleaned_data["code"], ProductBarcode.Kind.INTERNAL, actor=request.user)
            messages.success(request, "Code-barres du produit enregistré.")
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Le code-barres est invalide.")
    return redirect("products:detail", pk=product_pk)


@login_required
def barcode_generate(request, product_pk, variant_pk):
    _catalogue_manager(request)
    variant = get_object_or_404(ProductVariant, pk=variant_pk, product_id=product_pk)
    if request.method == "POST":
        ProductBarcodeService.generate_internal_code(variant, actor=request.user)
        messages.success(request, "Nouveau code-barres interne généré.")
    return redirect("products:detail", pk=product_pk)


@login_required
def barcode_deactivate(request, product_pk, variant_pk, barcode_pk):
    _catalogue_manager(request)
    alias = get_object_or_404(ProductBarcode, pk=barcode_pk, variant_id=variant_pk, variant__product_id=product_pk)
    if request.method == "POST":
        ProductBarcodeService.deactivate_alias(alias)
        messages.success(request, "Code-barres désactivé.")
    return redirect("products:detail", pk=product_pk)


@login_required
def barcode_print(request, product_pk, variant_pk):
    _catalogue_manager(request)
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=variant_pk, product_id=product_pk)
    aliases = variant.barcode_aliases.filter(active=True).order_by("-created_at", "code")
    if not aliases.exists():
        aliases = [ProductBarcodeService.ensure_internal_code(variant, actor=request.user)]
    printable = [{"alias": alias, "svg": barcode_svg(alias.code)} for alias in aliases]
    return render(request, "products/barcodes_print.html", {"variant": variant, "aliases": printable})


@login_required
def price_labels_print(request):
    _catalogue_manager(request)
    variants = list(ProductVariant.objects.filter(active=True, product__active=True).select_related("product").prefetch_related("barcode_aliases").order_by("product__name", "name"))
    for variant in variants:
        ProductBarcodeService.ensure_internal_code(variant, actor=request.user)
    return render(request, "products/price_labels.html", {"variants": variants})


@login_required
def category_list(request):
    _category_admin(request)
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Catégorie créée.")
        return redirect("products:category-list")
    categories = Category.objects.select_related("parent").prefetch_related("products").order_by("name")
    return render(request, "products/categories.html", {"categories": Paginator(categories, 20).get_page(request.GET.get("page")), "form": form})


@login_required
def category_update(request, pk):
    _category_admin(request)
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect("products:category-list")
    return render(request, "products/category_form.html", {"form": form, "category": category})


@login_required
def category_delete(request, pk):
    _category_admin(request)
    if request.method != "POST":
        return redirect("products:category-list")
    category = get_object_or_404(Category, pk=pk)
    try:
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    except ProtectedError:
        messages.error(request, "Cette catégorie est utilisée par des articles : réaffectez-les ou désactivez la catégorie avant suppression.")
    return redirect("products:category-list")


@login_required
def category_quick_create(request):
    _category_admin(request)
    if request.method != "POST":
        raise PermissionDenied
    form = QuickCategoryForm(request.POST)
    if form.is_valid():
        category = Category.objects.create(name=form.cleaned_data["name"])
        return render(request, "products/partials/category_quick_response.html", {"categories": Category.objects.filter(active=True).order_by("name"), "selected_category": category.pk, "message": f"Catégorie « {category.name} » créée et sélectionnée."})
    return render(request, "products/partials/category_quick_response.html", {"categories": Category.objects.filter(active=True).order_by("name"), "selected_category": request.POST.get("category"), "error": form.errors["name"].as_text()})
