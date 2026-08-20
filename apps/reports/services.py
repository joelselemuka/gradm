from decimal import Decimal, ROUND_HALF_UP
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import StoreSettings
from apps.expenses.models import Expense
from apps.pos.models import CashSession, CashTransaction
from apps.pos.selectors import cash_report_for
from apps.sales.models import Invoice


ZERO = Decimal("0.00")
logger = logging.getLogger(__name__)


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt(value):
    """Format report amounts with a dot thousands separator."""
    amount = _money(value)
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", ".")
    return f"{amount:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _status(value):
    value = _money(value)
    if value > ZERO:
        return "Surplus"
    if value < ZERO:
        return "Manquant"
    return "Conforme"


def report_recipient():
    """Return the configured recipient, with the environment as a safe fallback."""
    configured = (StoreSettings.get_solo().report_recipient_email or "").strip()
    return configured or (getattr(settings, "ADMIN_REPORT_EMAIL", "") or "").strip()


def build_report_data(day=None):
    """Build the sales/cash ledger described in modele_rapport_general.md."""
    day = day or timezone.localdate()
    invoices = Invoice.objects.validated().filter(created_at__date=day)
    expenses = Expense.objects.filter(
        status=Expense.Status.APPROVED,
        expense_date=day,
    ).select_related("requester", "cash_session__register").order_by("created_at")
    sessions = list(
        CashSession.objects.select_related("register", "cashier")
        .filter(opened_at__date=day)
        .order_by("pk")
    )
    cash_reports = [(session, cash_report_for(session)) for session in sessions]

    total_sales = _money(invoices.aggregate(total=Sum("total"))["total"])
    total_expenses = _money(expenses.aggregate(total=Sum("amount"))["total"])
    sales_balance = _money(total_sales - total_expenses)

    # Les dépenses appartiennent au rapport de vente et ne doivent pas être
    # comptées parmi les sorties du cash.
    movements = CashTransaction.objects.filter(
        session__in=sessions,
        voided_at__isnull=True,
    ).exclude(
        category__in=[CashTransaction.Category.OPENING_FLOAT, CashTransaction.Category.EXPENSE]
    ).select_related("session__register", "session__cashier", "created_by").order_by("created_at", "pk")
    cash_entries = list(movements.filter(direction=CashTransaction.Direction.IN))
    cash_outings = list(movements.filter(direction=CashTransaction.Direction.OUT))

    opening_local = _money(sum((report.opening_float for _, report in cash_reports), ZERO))
    opening_foreign = _money(sum((report.opening_foreign for _, report in cash_reports), ZERO))
    entries_local = _money(sum((movement.amount or ZERO for movement in cash_entries), ZERO))
    entries_foreign = _money(sum((movement.foreign_amount or ZERO for movement in cash_entries), ZERO))
    outings_local = _money(sum((movement.amount or ZERO for movement in cash_outings), ZERO))
    outings_foreign = _money(sum((movement.foreign_amount or ZERO for movement in cash_outings), ZERO))
    cash_balance_local = _money(opening_local + entries_local - outings_local)
    cash_balance_foreign = _money(opening_foreign + entries_foreign - outings_foreign)

    closed_sessions = [session for session in sessions if session.status == CashSession.Status.CLOSED]
    sales_deposit_local = _money(sum((session.sales_deposit_local_amount or ZERO for session in closed_sessions), ZERO))
    sales_deposit_foreign = _money(sum((session.sales_deposit_foreign_amount or ZERO for session in closed_sessions), ZERO))
    cash_deposit_local = _money(sum((session.counted_local_amount or ZERO for session in closed_sessions), ZERO))
    cash_deposit_foreign = _money(sum((session.counted_foreign_amount or ZERO for session in closed_sessions), ZERO))

    general_balance_local = _money(sales_balance + cash_balance_local)
    general_balance_foreign = cash_balance_foreign
    deposit_balance_local = _money(sales_deposit_local + cash_deposit_local)
    deposit_balance_foreign = _money(sales_deposit_foreign + cash_deposit_foreign)
    difference_local = _money(general_balance_local - deposit_balance_local)
    difference_foreign = _money(general_balance_foreign - deposit_balance_foreign)
    rate = _money(StoreSettings.get_solo().exchange_rate)
    cash_fc_equivalent = _money(cash_balance_local + cash_balance_foreign * rate)
    general_fc = _money(general_balance_local + general_balance_foreign * rate)

    session_rows = []
    for session, report in cash_reports:
        session_rows.append({
            "session": session,
            "cash": report,
            "sales_deposit_local": _money(session.sales_deposit_local_amount),
            "sales_deposit_foreign": _money(session.sales_deposit_foreign_amount),
            "cash_deposit_local": _money(session.counted_local_amount),
            "cash_deposit_foreign": _money(session.counted_foreign_amount),
            "sales_status": _status(session.sales_difference) if session.status == CashSession.Status.CLOSED else "Ouverte",
            "cash_status": _status(session.difference) if session.status == CashSession.Status.CLOSED else "Ouverte",
        })

    return {
        "day": day,
        "invoices": invoices,
        "expenses": expenses,
        "sessions": sessions,
        "session_rows": session_rows,
        "cash_entries": cash_entries,
        "cash_outings": cash_outings,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "sales_balance": sales_balance,
        "opening_local": opening_local,
        "opening_foreign": opening_foreign,
        "entries_local": entries_local,
        "entries_foreign": entries_foreign,
        "outings_local": outings_local,
        "outings_foreign": outings_foreign,
        "cash_balance_local": cash_balance_local,
        "cash_balance_foreign": cash_balance_foreign,
        "sales_deposit_local": sales_deposit_local,
        "sales_deposit_foreign": sales_deposit_foreign,
        "cash_deposit_local": cash_deposit_local,
        "cash_deposit_foreign": cash_deposit_foreign,
        "general_balance_local": general_balance_local,
        "general_balance_foreign": general_balance_foreign,
        "deposit_balance_local": deposit_balance_local,
        "deposit_balance_foreign": deposit_balance_foreign,
        "difference_local": difference_local,
        "difference_foreign": difference_foreign,
        "difference_local_abs": _money(abs(difference_local)),
        "difference_foreign_abs": _money(abs(difference_foreign)),
        "difference_status_local": _status(difference_local),
        "difference_status_foreign": _status(difference_foreign),
        "cash_fc_equivalent": cash_fc_equivalent,
        "general_fc": general_fc,
        "rate": rate,
    }


def _movement_text(movement):
    local = f"{_fmt(movement.amount)} FC" if movement.amount else "0 FC"
    foreign = f"{_fmt(movement.foreign_amount)} USD" if movement.foreign_amount else "0 USD"
    label = movement.label or movement.description or "Opération"
    return f"- {label} : {local} & {foreign}"


def build_general_report(day=None):
    data = build_report_data(day)
    expense_lines = [
        f"- {expense.category} — {expense.description or 'Sans motif'} : {_fmt(expense.amount)} FC"
        for expense in data["expenses"]
    ]
    session_lines = [
        f"- {row['session'].register.name} / {row['session'].cashier.username} (session {row['session'].pk})"
        for row in data["session_rows"]
    ]
    entry_lines = [_movement_text(movement) for movement in data["cash_entries"]]
    outing_lines = [_movement_text(movement) for movement in data["cash_outings"]]
    local_observation = f"{data['difference_status_local']} de {_fmt(abs(data['difference_local']))} FC"
    foreign_observation = f"{data['difference_status_foreign']} de {_fmt(abs(data['difference_foreign']))} USD"
    lines = [
        f"# Rapport général de vente et du cash du {data['day']:%d/%m/%Y}",
        "### Vente effectuée par (session)",
        *(session_lines or ["- Aucune session enregistrée"]),
        "",
        "## VENTE DU JOUR",
        f"### Total vendu : {_fmt(data['total_sales'])} FC",
        "### Dépenses",
        *(expense_lines or ["- Aucune dépense approuvée"]),
        f"#### Total sortie : {_fmt(data['total_expenses'])} FC",
        f"### Solde vente : {_fmt(data['sales_balance'])} FC",
        f"### Versement vente : {_fmt(data['sales_deposit_local'])} FC & {_fmt(data['sales_deposit_foreign'])} USD",
        "",
        "--------------------------------------------------------------------------------",
        "",
        f"## CASH DU JOUR : {_fmt(data['opening_local'])} FC & {_fmt(data['opening_foreign'])} USD",
        "### Sorties :",
        *(outing_lines or ["- Aucune sortie"]),
        f"#### Total sorties : {_fmt(data['outings_local'])} FC & {_fmt(data['outings_foreign'])} USD",
        "### Entrées :",
        *(entry_lines or ["- Aucune entrée"]),
        f"#### Total entrées : {_fmt(data['entries_local'])} FC & {_fmt(data['entries_foreign'])} USD",
        f"### Solde cash : {_fmt(data['cash_balance_local'])} FC & {_fmt(data['cash_balance_foreign'])} USD",
        f"### Versement cash : {_fmt(data['cash_deposit_local'])} FC & {_fmt(data['cash_deposit_foreign'])} USD",
        f"### Solde général : {_fmt(data['general_balance_local'])} FC & {_fmt(data['general_balance_foreign'])} USD",
        f"### Solde versement : {_fmt(data['deposit_balance_local'])} FC & {_fmt(data['deposit_balance_foreign'])} USD",
        f"## Observation : solde général - solde versement = {local_observation} ; {foreign_observation}",
    ]
    return {
        **data,
        "subject": f"Rapport général — {data['day']:%d/%m/%Y}",
        "body": "\n".join(lines),
        "recipient": report_recipient(),
    }


def send_general_report(day=None, *, fail_silently=False):
    report = build_general_report(day)
    if not report["recipient"]:
        return False
    try:
        send_mail(
            report["subject"],
            report["body"],
            settings.DEFAULT_FROM_EMAIL,
            [report["recipient"]],
            fail_silently=fail_silently,
        )
    except Exception:
        logger.exception("Impossible d'envoyer le rapport général à %s", report["recipient"])
        if not fail_silently:
            raise
        return False
    return True
