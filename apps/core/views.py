from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from apps.expenses.models import Expense
from apps.inventory.models import StockLot
from apps.pos.models import CashSession
from apps.sales.models import Invoice, InvoiceLine
from apps.audit.services import audit
from .forms import StoreSettingsForm
from .models import StoreSettings
from .date_filters import get_date_range


@login_required
def dashboard(request):
    date_range = get_date_range(request.GET)
    start, end = date_range["start"], date_range["end"]
    cutoff = timezone.localdate()
    active_session = CashSession.objects.filter(
        cashier=request.user,
        status=CashSession.Status.OPEN,
    ).first() if request.user.can_operate_pos() else None
    invoices = Invoice.objects.validated()
    if not request.user.can_cancel_invoice():
        invoices = invoices.filter(cash_session=active_session) if active_session else invoices.none()
    period_invoices = invoices.filter(created_at__date__gte=start, created_at__date__lte=end)
    recent_sales = period_invoices.select_related("cashier").order_by("-created_at")[:6]

    if date_range["days"] <= 31:
        buckets = {
            row["bucket"]: row["total"] or 0
            for row in period_invoices.annotate(bucket=TruncDate("created_at")).values("bucket").annotate(total=Sum("total"))
        }
        daily_revenue = []
        current = start
        while current <= end:
            daily_revenue.append({"date": current, "label": current.strftime("%d/%m"), "amount": buckets.get(current, 0)})
            current += timedelta(days=1)
    else:
        buckets = {
            (row["bucket"].date() if hasattr(row["bucket"], "date") else row["bucket"]): row["total"] or 0
            for row in period_invoices.annotate(bucket=TruncMonth("created_at")).values("bucket").annotate(total=Sum("total"))
        }
        daily_revenue = []
        current = start.replace(day=1)
        while current <= end:
            daily_revenue.append({"date": current, "label": current.strftime("%b %Y"), "amount": buckets.get(current, 0)})
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    chart_max = max((item["amount"] for item in daily_revenue), default=0) or 1
    for item in daily_revenue:
        item["height"] = max(6, int(item["amount"] * 100 / chart_max)) if item["amount"] else 3
    product_sales = list(InvoiceLine.objects.filter(invoice__in=period_invoices).values("product_name", "variant_name").annotate(quantity=Sum("quantity"), revenue=Sum("line_total")))
    most_sold_products = sorted(product_sales, key=lambda item: (-item["quantity"], item["product_name"], item["variant_name"]))[:5]
    least_sold_products = sorted(product_sales, key=lambda item: (item["quantity"], item["product_name"], item["variant_name"]))[:5]
    product_max_quantity = max((item["quantity"] for item in product_sales), default=1)
    for item in most_sold_products + least_sold_products:
        item["bar_width"] = max(8, int(item["quantity"] * 100 / product_max_quantity))
    expense_queryset = Expense.objects.filter(status=Expense.Status.APPROVED, expense_date__gte=start, expense_date__lte=end)
    if not request.user.can_cancel_invoice():
        expense_queryset = expense_queryset.filter(cash_session=active_session) if active_session else expense_queryset.none()
    period_revenue = period_invoices.aggregate(total=Sum("total"))["total"] or 0
    period_expenses = expense_queryset.aggregate(total=Sum("amount"))["total"] or 0
    context = {
        "today_revenue": period_revenue,
        "today_sales": period_invoices.count(),
        "week_revenue": period_revenue,
        "month_revenue": period_revenue,
        "period_revenue": period_revenue,
        "period_sales": period_invoices.count(),
        "period_expenses": period_expenses,
        "period_net": period_revenue - period_expenses,
        "low_stock": StockLot.objects.low_stock().count() if request.user.can_manage_inventory() else 0,
        "expiring_lots": StockLot.objects.expiring().count() if request.user.can_manage_inventory() else 0,
        "expired_lots": StockLot.objects.filter(expires_at__lt=cutoff, quantity_available__gt=0).count() if request.user.can_manage_inventory() else 0,
        "approved_expenses": expense_queryset.aggregate(total=Sum("amount"))["total"] or 0,
        "open_registers": CashSession.objects.filter(status=CashSession.Status.OPEN).count() if request.user.can_manage_catalogue() else CashSession.objects.filter(status=CashSession.Status.OPEN, cashier=request.user).count(),
        "recent_sales": recent_sales,
        "daily_revenue": daily_revenue,
        "most_sold_products": most_sold_products,
        "least_sold_products": least_sold_products,
        "range_start": start,
        "range_end": end,
        "selected_date": date_range["selected_date"],
        "date_from": date_range["date_from"],
        "date_to": date_range["date_to"],
        "selected_period": date_range["period"],
        "period_label": date_range["period_label"],
    }
    return render(request, "dashboard/index.html", context)


@login_required
def dashboard_expenses(request):
    date_range = get_date_range(request.GET)
    expenses = Expense.objects.filter(status=Expense.Status.APPROVED, expense_date__gte=date_range["start"], expense_date__lte=date_range["end"])
    if not request.user.can_cancel_invoice():
        active_session = CashSession.objects.filter(cashier=request.user, status=CashSession.Status.OPEN).first()
        expenses = expenses.filter(cash_session=active_session) if active_session else expenses.none()
    amount = expenses.aggregate(total=Sum("amount"))["total"] or 0
    return render(request, "dashboard/partials/expenses_stat.html", {"approved_expenses": amount, "range_start": date_range["start"], "range_end": date_range["end"]})


@login_required
def store_settings(request):
    if not request.user.can_manage_cash():
        raise PermissionDenied("Seul un administrateur peut modifier la configuration.")
    settings = StoreSettings.get_solo()
    form = StoreSettingsForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        settings = form.save()
        audit(actor=request.user, action="STORE_SETTINGS_UPDATED", target=settings, after={"discounts_enabled": settings.discounts_enabled, "promotion_enabled": settings.promotion_enabled, "exchange_rate": str(settings.exchange_rate)})
        messages.success(request, "Configuration enregistrée.")
        return redirect("core:settings")
    return render(request, "core/settings.html", {"form": form, "store_settings": settings})
