from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.pos.models import CashSession
from apps.products.models import ProductBarcode, ProductVariant
from apps.core.models import StoreSettings
from apps.core.date_filters import get_date_range
from .forms import CancellationForm, CheckoutForm
from .models import Invoice, Payment
from .services import InvoiceService, SaleItem, SaleService


def _cart(request):
    return {int(key): int(value) for key, value in request.session.get("pos_cart", {}).items() if int(value) > 0}


def _save_cart(request, cart):
    request.session["pos_cart"] = {str(key): value for key, value in cart.items() if value > 0}
    request.session.modified = True


def _draft_invoice_number(request, create=False):
    number = request.session.get("pos_invoice_number")
    if not number and create:
        number = SaleService.generate_invoice_number()
        request.session["pos_invoice_number"] = number
        request.session.modified = True
    return number


def _cart_context(request):
    cart = _cart(request)
    variants = ProductVariant.objects.select_related("product").filter(pk__in=cart, active=True, product__active=True)
    items = []
    total = Decimal("0")
    for variant in variants:
        quantity = cart[variant.pk]
        line_total = variant.sale_price * quantity
        items.append({"variant": variant, "quantity": quantity, "line_total": line_total})
        total += line_total
    return items, total


def _active_session(request):
    return CashSession.objects.filter(cashier=request.user, status=CashSession.Status.OPEN).select_related("register").first()


def _require_active_session(request):
    """The POS is strictly bound to the currently authenticated cashier session."""
    if not request.user.can_operate_pos():
        raise PermissionDenied("Accès POS non autorisé.")
    session = _active_session(request)
    if session is None:
        raise PermissionDenied("Une session de vente ouverte à votre nom est obligatoire pour accéder au POS.")
    return session


def _product_search_queryset(query=""):
    queryset = ProductVariant.objects.select_related("product").filter(active=True, product__active=True).order_by("product__name", "name")
    if not query:
        return queryset[:20]
    search_filter = Q(sku__icontains=query) | Q(barcode__icontains=query) | Q(manufacturer_barcode__icontains=query) | Q(store_barcode__icontains=query) | Q(barcode_aliases__code__icontains=query, barcode_aliases__active=True) | Q(product__name__icontains=query) | Q(product__internal_reference__icontains=query) | Q(name__icontains=query)
    if query.isdigit():
        search_filter |= Q(pk=int(query))
    return queryset.filter(search_filter).distinct()[:20]


def _exact_scanned_variant(query):
    if not query:
        return None
    matches = ProductVariant.objects.select_related("product").filter(
        Q(barcode__iexact=query) | Q(manufacturer_barcode__iexact=query) | Q(store_barcode__iexact=query) | Q(barcode_aliases__code__iexact=query, barcode_aliases__active=True),
        active=True,
        product__active=True,
    ).distinct()
    return matches.first() if matches.count() == 1 else None


@login_required
def pos(request):
    if request.user.can_cancel_invoice():
        date_range = get_date_range(request.GET)
        filtered_invoices = Invoice.objects.validated().filter(
            created_at__date__gte=date_range["start"],
            created_at__date__lte=date_range["end"],
        )
        invoices = Paginator(filtered_invoices.select_related("cashier", "cash_session__register").order_by("-created_at"), 30).get_page(request.GET.get("page"))
        totals = filtered_invoices.aggregate(
            gross=Sum("subtotal"),
            promotion=Sum("promotion_discount"),
            manual=Sum("manual_discount"),
            net=Sum("total"),
        )
        return render(request, "sales/pos_admin.html", {
            "invoices": invoices,
            "invoice_count": filtered_invoices.count(),
            "gross_total": totals["gross"] or Decimal("0"),
            "discount_total": (totals["promotion"] or Decimal("0")) + (totals["manual"] or Decimal("0")),
            "net_total": totals["net"] or Decimal("0"),
            "range_start": date_range["start"],
            "range_end": date_range["end"],
            "selected_date": date_range["selected_date"],
            "date_from": date_range["date_from"],
            "date_to": date_range["date_to"],
            "selected_period": date_range["period"],
            "period_label": date_range["period_label"],
        })
    session = _require_active_session(request)
    query = request.GET.get("q", "").strip()
    results = _product_search_queryset(query)
    if request.headers.get("HX-Request") == "true":
        return render(request, "sales/partials/product_results.html", {"results": results, "query": query, "auto_add": _exact_scanned_variant(query) is not None})
    items, total = _cart_context(request)
    store_settings = StoreSettings.get_solo()
    return render(request, "sales/pos.html", {"session": session, "query": query, "results": results, "cart_items": items, "cart_total": total, "draft_invoice_number": _draft_invoice_number(request, create=bool(items)), "checkout_form": CheckoutForm(store_settings=store_settings), "store_settings": store_settings})


@login_required
def cart_add(request):
    if request.method != "POST": raise Http404
    _require_active_session(request)
    variant = get_object_or_404(ProductVariant, pk=request.POST.get("variant_id"), active=True, product__active=True)
    cart = _cart(request); cart[variant.pk] = cart.get(variant.pk, 0) + 1; _save_cart(request, cart)
    draft_invoice_number = _draft_invoice_number(request, create=True)
    if request.headers.get("HX-Request") == "true":
        query = request.POST.get("q", "").strip()
        items, total = _cart_context(request)
        response = render(request, "sales/partials/product_results_response.html", {"results": _product_search_queryset(query), "query": query, "auto_add": False, "cart_items": items, "cart_total": total, "draft_invoice_number": draft_invoice_number})
        response["HX-Trigger"] = "pos-cart-added"
        return response
    return redirect("sales:pos")


@login_required
def cart_update(request, variant_id):
    if request.method != "POST": raise Http404
    _require_active_session(request)
    cart = _cart(request)
    remove = request.POST.get("remove") == "1"
    try: quantity = int(request.POST.get("quantity", 0))
    except (TypeError, ValueError): quantity = 0
    error = None
    if remove:
        cart.pop(variant_id, None)
    elif quantity >= 1:
        cart[variant_id] = quantity
    else:
        error = "La quantité doit être au moins égale à 1."
    _save_cart(request, cart)
    if not cart:
        request.session.pop("pos_invoice_number", None)
    if request.headers.get("HX-Request") == "true":
        items, total = _cart_context(request)
        return render(request, "sales/partials/pos_cart_update_response.html", {"cart_items": items, "cart_total": total, "draft_invoice_number": _draft_invoice_number(request), "cart_error": error})
    return redirect("sales:pos")


@login_required
def checkout(request):
    if request.method != "POST": raise Http404
    session = _require_active_session(request)
    form = CheckoutForm(request.POST, store_settings=StoreSettings.get_solo())
    items, _ = _cart_context(request)
    if not form.is_valid() or not items:
        messages.error(request, "Le panier ou le paiement est invalide.")
        return redirect("sales:pos")
    try:
        invoice = SaleService.create_sale(actor=request.user, cash_session=session, payment_method=Payment.Method.CASH, invoice_number=_draft_invoice_number(request, create=True), items=[SaleItem(item["variant"].pk, item["quantity"]) for item in items], **form.cleaned_data)
        _save_cart(request, {})
        request.session.pop("pos_invoice_number", None)
        request.session.modified = True
        messages.success(request, f"Vente {invoice.number} validée.")
        invoice_url = f"{reverse('sales:invoice-detail', kwargs={'pk': invoice.pk})}?print=1"
        # Couverture du cas où le fragment de modal est soumis via HTMX.
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse(status=204)
            response["HX-Redirect"] = invoice_url
            return response
        return redirect(invoice_url)
    except IntegrityError:
        # Le numéro de facture existe déjà : double clic ou retry réseau.
        # On redirige vers la facture déjà créée plutôt que d'afficher une erreur 500.
        existing_number = request.session.get("pos_invoice_number")
        if existing_number:
            existing = Invoice.objects.filter(number=existing_number).first()
            if existing:
                _save_cart(request, {})
                request.session.pop("pos_invoice_number", None)
                request.session.modified = True
                messages.info(request, f"La vente {existing.number} a déjà été enregistrée.")
                invoice_url = f"{reverse('sales:invoice-detail', kwargs={'pk': existing.pk})}?print=1"
                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = invoice_url
                    return response
                return redirect(invoice_url)
        messages.error(request, "Erreur lors de la création de la vente. Veuillez réessayer.")
        return redirect("sales:pos")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return redirect("sales:pos")


@login_required
def checkout_preview(request):
    """Render a server-calculated receipt preview without creating a sale."""
    if request.method != "POST":
        raise Http404
    session = _require_active_session(request)
    form = CheckoutForm(request.POST, store_settings=StoreSettings.get_solo())
    items, _ = _cart_context(request)
    context = {"form": form, "session": session, "draft_invoice_number": _draft_invoice_number(request, create=bool(items))}
    if not items:
        context["preview_error"] = "Ajoutez au moins un article au panier avant de continuer."
        return render(request, "sales/partials/checkout_preview.html", context)
    if not form.is_valid():
        context["preview_error"] = "Vérifiez les informations de paiement avant de continuer."
        return render(request, "sales/partials/checkout_preview.html", context)
    try:
        context["quote"] = SaleService.quote_sale(
            items=[SaleItem(item["variant"].pk, item["quantity"]) for item in items],
            manual_discount=form.cleaned_data["manual_discount"],
        )
    except ValidationError as exc:
        context["preview_error"] = "; ".join(exc.messages)
        return render(request, "sales/partials/checkout_preview.html", context)
    return render(request, "sales/partials/checkout_preview.html", context)


@login_required
def invoice_list(request):
    invoices = Invoice.objects.select_related("cashier", "cash_session__register").prefetch_related("payments").order_by("-created_at")
    registers = CashSession.objects.select_related("register").values_list("register_id", "register__name").distinct().order_by("register__name")
    selected_date = request.GET.get("date") or str(timezone.localdate())
    selected_register = request.GET.get("register", "")
    if request.user.can_cancel_invoice():
        invoices = invoices.filter(created_at__date=selected_date)
        if selected_register.isdigit(): invoices = invoices.filter(cash_session__register_id=selected_register)
    else:
        # Sales history is scoped to the exact open session.  Filtering by
        # cashier alone would leak invoices from a previous closed session
        # when the same user starts a new one.
        active_session = _active_session(request)
        invoices = invoices.filter(cash_session=active_session) if active_session else invoices.none()
    query = request.GET.get("q", "").strip()
    if query: invoices = invoices.filter(Q(number__icontains=query) | Q(cashier__username__icontains=query))
    return render(request, "sales/invoices.html", {"invoices": Paginator(invoices, 20).get_page(request.GET.get("page")), "query": query, "selected_date": selected_date, "selected_register": selected_register, "registers": registers, "is_admin_view": request.user.can_cancel_invoice()})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("cashier", "cash_session__register").prefetch_related("lines", "payments"), pk=pk)
    if not request.user.can_cancel_invoice():
        active_session = _active_session(request)
        if not active_session or invoice.cash_session_id != active_session.pk:
            raise PermissionDenied("Cette facture appartient à une autre session de vente.")
    print_on_load = request.GET.get("print") == "1"
    context = {
        "invoice": invoice,
        "cancellation_form": CancellationForm(),
        "cancellation_allowed": (
            request.user.can_cancel_invoice()
            and invoice.status == Invoice.Status.VALIDATED
            and invoice.created_at.date() == timezone.localdate()
            and (invoice.cash_session is None or invoice.cash_session.status == invoice.cash_session.Status.OPEN)
        ),
        "print_on_load": print_on_load,
    }
    if print_on_load:
        context["store_settings"] = StoreSettings.get_solo()
        return render(request, "sales/invoice_ticket.html", context)
    return render(request, "sales/invoice_detail.html", context)


@login_required
def cancel_invoice(request, pk):
    if request.method != "POST": raise Http404
    invoice = get_object_or_404(Invoice, pk=pk)
    form = CancellationForm(request.POST)
    if form.is_valid():
        try:
            InvoiceService.cancel_invoice(invoice=invoice, actor=request.user, reason=form.cleaned_data["reason"])
            messages.success(request, "Facture annulée, stock restauré et audit créé.")
        except (ValidationError, PermissionDenied) as exc: messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("sales:invoice-detail", pk=invoice.pk)
