from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import redirect, render
from .forms import InventoryCountForm, InventoryCountLineForm, StockIssueForm, StockReceiptForm, StockIssueLineForm, StockReceiptLineForm, StockOperationForm
from .models import InventoryCount, InventoryCountLine, StockLot, StockMovement
from .services import InventoryService
from apps.products.models import ProductVariant
from .alerts import expired_rows, expiring_rows, low_stock_rows


def _inventory_manager(request):
    if not request.user.can_manage_inventory(): raise PermissionDenied("Accès stock non autorisé.")


@login_required
def alert_list(request, kind):
    _inventory_manager(request)
    if kind == "expired":
        rows, title, description = expired_rows(), "Produits expirés", "Articles encore en stock dont la date d'expiration est dépassée."
    elif kind == "expiring":
        rows, title, description = expiring_rows(), "Produits bientôt expirés", "Articles dont la date d'expiration arrive dans les 60 prochains jours."
    elif kind == "low-stock":
        rows, title, description = low_stock_rows(), "Stock faible", "Produits dont le stock disponible est inférieur ou égal au seuil défini."
        variant = request.GET.get("variant")
        if variant and variant.isdigit():
            rows = [item for item in rows if item.pk == int(variant)]
    else:
        raise PermissionDenied("Type d'alerte invalide.")
    return render(request, "inventory/alerts.html", {"rows": Paginator(rows, 20).get_page(request.GET.get("page")), "alert_type": kind, "title": title, "description": description})


@login_required
def stock_list(request):
    _inventory_manager(request)
    lots = StockLot.objects.select_related("variant__product").order_by("expires_at", "variant__product__name")
    variants = ProductVariant.objects.select_related("product", "product__category").annotate(current_stock=Sum("lots__quantity_available")).order_by("product__name", "name")
    return render(request, "inventory/list.html", {"lots": Paginator(lots, 20).get_page(request.GET.get("lots_page")), "stock_items": Paginator(variants, 20).get_page(request.GET.get("page")), "receipt_form": StockReceiptForm(), "issue_form": StockIssueForm()})


def _bulk_lines(request, line_form_class, fields):
    values = {field: request.POST.getlist(field) for field in fields}
    count = max((len(items) for items in values.values()), default=0)
    lines, errors = [], []
    for index in range(count):
        data = {field: (values[field][index] if index < len(values[field]) else "") for field in fields}
        if not any(str(value).strip() for value in data.values()):
            continue
        form = line_form_class(data)
        if form.is_valid():
            lines.append(form.cleaned_data)
        else:
            errors.append(f"Article {index + 1} : corrigez les champs indiqués.")
    return lines, errors


@login_required
def operations(request):
    _inventory_manager(request)
    variants = ProductVariant.objects.select_related("product").filter(active=True, product__active=True).order_by("product__name", "sku")
    selected_variant = request.GET.get("variant", "")
    mode = request.GET.get("mode", "receive") if request.method == "GET" else request.POST.get("mode", "receive")
    return render(request, "inventory/operations.html", {"variants": variants, "selected_variant": selected_variant, "mode": mode if mode in {"receive", "issue"} else "receive"})


@login_required
def receive_bulk(request):
    _inventory_manager(request)
    if request.method != "POST":
        return redirect("inventory:operations")
    operation = StockOperationForm(request.POST)
    lines, errors = _bulk_lines(request, StockReceiptLineForm, ("variant", "quantity", "lot_code", "expires_at"))
    if operation.is_valid() and not errors:
        try:
            InventoryService.receive_batch(lines=lines, actor=request.user, reference=operation.cleaned_data["reference"])
            messages.success(request, f"Réception {operation.cleaned_data['reference']} enregistrée pour {len(lines)} article(s).")
            return redirect("inventory:list")
        except ValidationError as exc:
            errors = exc.messages
    for error in errors:
        messages.error(request, error)
    if not operation.is_valid():
        messages.error(request, "La référence de réception est obligatoire.")
    return redirect("inventory:operations")


@login_required
def issue_bulk(request):
    _inventory_manager(request)
    if request.method != "POST":
        return redirect("inventory:operations")
    operation = StockOperationForm(request.POST)
    lines, errors = _bulk_lines(request, StockIssueLineForm, ("variant", "quantity"))
    if operation.is_valid() and not errors:
        try:
            InventoryService.issue_batch(lines=lines, actor=request.user, reference=operation.cleaned_data["reference"], reason=operation.cleaned_data["reason"])
            messages.success(request, f"Sortie {operation.cleaned_data['reference']} enregistrée pour {len(lines)} article(s).")
            return redirect("inventory:list")
        except ValidationError as exc:
            errors = exc.messages
    for error in errors:
        messages.error(request, error)
    if not operation.is_valid():
        messages.error(request, "La référence et le motif de sortie sont obligatoires.")
    return redirect("inventory:operations")


@login_required
def receive_stock(request):
    _inventory_manager(request)
    if request.method != "POST": return redirect("inventory:list")
    form = StockReceiptForm(request.POST)
    if form.is_valid():
        try:
            InventoryService.receive(actor=request.user, **form.cleaned_data)
            messages.success(request, "Reception enregistrée : stock et mouvement créés.")
        except ValidationError as exc: messages.error(request, "; ".join(exc.messages))
    else: messages.error(request, "Veuillez corriger les informations de réception.")
    return redirect("inventory:list")


@login_required
def issue_stock(request):
    _inventory_manager(request)
    if request.method != "POST": return redirect("inventory:list")
    form = StockIssueForm(request.POST)
    if form.is_valid():
        try:
            InventoryService.issue(variant=form.cleaned_data["variant"], quantity=form.cleaned_data["quantity"], actor=request.user, reason=form.cleaned_data["reason"], reference=f"SORTIE-{request.user.pk}")
            messages.success(request, "Sortie enregistrée : le stock et le mouvement ont été mis à jour.")
        except ValidationError as exc: messages.error(request, "; ".join(exc.messages))
    else: messages.error(request, "Veuillez corriger les informations de sortie.")
    return redirect("inventory:list")


@login_required
def movement_list(request):
    _inventory_manager(request)
    from apps.inventory.models import StockMovement
    from django.db.models import Q

    query       = request.GET.get("q", "").strip()
    type_filter = request.GET.get("type", "")
    date_filter = request.GET.get("date", "")

    movements = StockMovement.objects.select_related(
        "lot__variant__product", "lot__variant", "actor"
    ).order_by("-created_at")

    if query:
        movements = movements.filter(
            Q(lot__variant__product__name__icontains=query)
            | Q(lot__variant__sku__icontains=query)
            | Q(lot__code__icontains=query)
            | Q(reference__icontains=query)
        )
    if type_filter:
        movements = movements.filter(movement_type=type_filter)
    if date_filter:
        movements = movements.filter(created_at__date=date_filter)

    return render(request, "inventory/movements.html", {
        "movements":      Paginator(movements, 20).get_page(request.GET.get("page")),
        "movement_types": StockMovement.Type.choices,
        "query":          query,
        "type_filter":    type_filter,
        "date_filter":    date_filter,
    })


@login_required
def count_list(request):
    _inventory_manager(request)
    counts = InventoryCount.objects.select_related("created_by", "completed_by").prefetch_related("lines")
    return render(request, "inventory/counts.html", {"counts": Paginator(counts, 20).get_page(request.GET.get("page")), "form": InventoryCountForm()})


@login_required
def count_create(request):
    _inventory_manager(request)
    form = InventoryCountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            count = InventoryService.start_count(actor=request.user, **form.cleaned_data)
            messages.success(request, "Inventaire démarré. Saisissez maintenant les quantités physiques.")
            return redirect("inventory:count-detail", pk=count.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(request, "inventory/count_form.html", {"form": form})


@login_required
def count_detail(request, pk):
    _inventory_manager(request)
    count = InventoryCount.objects.select_related("created_by", "completed_by").prefetch_related("lines__variant__product").get(pk=pk)
    return render(request, "inventory/count_detail.html", {"count": count, "lines": Paginator(count.lines.all(), 20).get_page(request.GET.get("page"))})


@login_required
def count_line_update(request, pk):
    _inventory_manager(request)
    line = InventoryCountLine.objects.select_related("count").get(pk=pk)
    if request.method == "POST":
        form = InventoryCountLineForm(request.POST)
        if form.is_valid():
            try:
                InventoryService.set_count_line(line=line, **form.cleaned_data)
                messages.success(request, "Quantité comptée enregistrée.")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        else:
            messages.error(request, "La quantité comptée est invalide.")
    return redirect("inventory:count-detail", pk=line.count_id)


@login_required
def count_complete(request, pk):
    _inventory_manager(request)
    count = InventoryCount.objects.get(pk=pk)
    if request.method == "POST":
        try:
            InventoryService.complete_count(count=count, actor=request.user)
            messages.success(request, "Inventaire clôturé et écarts appliqués au stock.")
            # ── Génération PDF + email ─────────────────────────────────────────
            _generate_and_send_inventory_report(count)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("inventory:count-detail", pk=pk)


def _generate_and_send_inventory_report(count):
    """Génère le PDF, le sauvegarde sur le modèle et l'envoie par email."""
    import logging
    from django.core.files.base import ContentFile
    from django.core.mail import EmailMessage
    from django.conf import settings
    from apps.core.models import StoreSettings
    from apps.inventory.pdf import generate_inventory_pdf

    logger = logging.getLogger(__name__)
    try:
        store = StoreSettings.get_solo()
        store_name = store.name or "Supermarché"
        pdf_bytes = generate_inventory_pdf(count, store_name=store_name)

        # Sauvegarde dans le champ FileField
        filename = f"inventaire_{count.reference}.pdf"
        count = InventoryCount.objects.get(pk=count.pk)   # refresh
        count.report_pdf.save(filename, ContentFile(pdf_bytes), save=True)

        # Email
        recipient = (store.report_recipient_email or "").strip() or (
            getattr(settings, "ADMIN_REPORT_EMAIL", "") or ""
        ).strip()
        if recipient:
            mail = EmailMessage(
                subject=f"Rapport d'inventaire — {count.reference}",
                body=(
                    f"Bonjour,\n\n"
                    f"Veuillez trouver ci-joint le rapport de l'inventaire {count.reference} "
                    f"clôturé le {count.completed_at.strftime('%d/%m/%Y à %H:%M')} "
                    f"par {count.completed_by.username if count.completed_by else '—'}.\n\n"
                    f"Cordialement,\n{store_name}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )
            mail.attach(filename, pdf_bytes, "application/pdf")
            mail.send(fail_silently=True)
            logger.info("Rapport inventaire %s envoyé à %s", count.reference, recipient)
    except Exception:
        logger.exception("Erreur lors de la génération/envoi du rapport d'inventaire %s", count.reference)
