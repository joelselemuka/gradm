from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from apps.expenses.models import Expense
from apps.inventory.models import StockLot
from apps.pos.models import CashSession
from apps.pos.selectors import cash_report_for
from apps.sales.models import Invoice
from apps.core.date_filters import get_date_range
from .services import build_report_data

ZERO = Decimal("0.00")


def _daily_situation(day):
    report = build_report_data(day)
    return {
        "date":                 day,
        "revenue":              report["total_sales"],
        "expenses":             report["total_expenses"],
        "cash":                 report["cash_fc_equivalent"],
        "net":                  report["sales_balance"],
        "invoice_count":        report["invoices"].count(),
        "session_count":        len(report["sessions"]),
        "closed_session_count": sum(1 for s in report["sessions"] if s.status == CashSession.Status.CLOSED),
        # Vente
        "sales_balance":        report["sales_balance"],
        "sales_deposit_local":  report["sales_deposit_local"],
        "sales_deposit_foreign":report["sales_deposit_foreign"],
        # Cash
        "cash_balance_local":   report["cash_balance_local"],
        "cash_balance_foreign": report["cash_balance_foreign"],
        "cash_deposit_local":   report["cash_deposit_local"],
        "cash_deposit_foreign": report["cash_deposit_foreign"],
        "outings_local":        report["outings_local"],
        "outings_foreign":      report["outings_foreign"],
        "entries_local":        report["entries_local"],
        "entries_foreign":      report["entries_foreign"],
        # Globaux
        "sales_difference":     report["difference_local"],
        "cash_difference":      report["difference_local"],
    }


def _allowed(request):
    if not request.user.can_manage_catalogue():
        raise PermissionDenied


@login_required
def report_home(request):
    _allowed(request)
    date_range = get_date_range(request.GET)
    report_type = request.GET.get("type", "") if request.GET.get("type", "") in {"sale", "cash"} else ""
    rows = []
    day = date_range["start"]
    while day <= date_range["end"]:
        situation = _daily_situation(day)
        if not report_type or report_type == "sale":
            rows.append({
                "date": day, "label": "Rapport de vente", "report_type": "sale",
                "total": situation["revenue"],
                "secondary": situation["expenses"], "secondary_label": "Dépenses approuvées",
                "count": situation["invoice_count"],
                "sales_balance":        situation["sales_balance"],
                "cash_balance_local":   ZERO,
                "cash_balance_foreign": ZERO,
                "sales_deposit_local":  situation["sales_deposit_local"],
                "sales_deposit_foreign":situation["sales_deposit_foreign"],
                "outings_local":        ZERO,
                "outings_foreign":      ZERO,
                "entries_local":        ZERO,
                "entries_foreign":      ZERO,
            })
        if not report_type or report_type == "cash":
            rows.append({
                "date": day, "label": "Rapport de cash", "report_type": "cash",
                "total": situation["cash"],
                "secondary": situation["session_count"], "secondary_label": "Sessions",
                "count": situation["session_count"],
                "sales_balance":        ZERO,
                "cash_balance_local":   situation["cash_balance_local"],
                "cash_balance_foreign": situation["cash_balance_foreign"],
                "sales_deposit_local":  situation["cash_deposit_local"],
                "sales_deposit_foreign":situation["cash_deposit_foreign"],
                "outings_local":        situation["outings_local"],
                "outings_foreign":      situation["outings_foreign"],
                "entries_local":        situation["entries_local"],
                "entries_foreign":      situation["entries_foreign"],
            })
        day += timedelta(days=1)
    return render(request, "reports/home.html", {
        "situations":  Paginator(rows, 20).get_page(request.GET.get("page")),
        "today":       _daily_situation(timezone.localdate()),
        "low_stock":   StockLot.objects.low_stock().count(),
        "date_range":  date_range,
        "report_type": report_type,
    })


@login_required
def report_detail(request, day):
    _allowed(request)
    try:
        selected_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise PermissionDenied("Date de rapport invalide.")
    invoices = Paginator(Invoice.objects.filter(created_at__date=selected_day).select_related("cashier", "cash_session__register").prefetch_related("payments").order_by("-created_at"), 30).get_page(request.GET.get("page"))
    expenses = Paginator(Expense.objects.filter(expense_date=selected_day).select_related("requester", "approved_by", "cash_session__register").order_by("-created_at"), 30).get_page(request.GET.get("page"))
    sessions = CashSession.objects.select_related("register", "cashier").filter(opened_at__date=selected_day)
    reports = Paginator([{"session": session, "cash": cash_report_for(session)} for session in sessions], 30).get_page(request.GET.get("page"))
    return render(request, "reports/detail.html", {
        "situation": _daily_situation(selected_day),
        "report": build_report_data(selected_day),
        "invoices": invoices,
        "expenses": expenses,
        "reports": reports,
    })
