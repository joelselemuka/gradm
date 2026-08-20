from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from apps.core.models import StoreSettings
from apps.expenses.models import Expense
from apps.pos.models import CashSession, CashTransaction
from apps.sales.models import Invoice, Payment


ZERO = Decimal("0.00")


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CashReport:
    session: CashSession
    exchange_rate: Decimal
    opening_float: Decimal
    opening_foreign: Decimal
    owner_deposits: Decimal
    owner_deposits_foreign: Decimal
    cash_sales: Decimal
    cash_sales_foreign: Decimal
    purchases: Decimal
    purchases_foreign: Decimal
    expenses: Decimal
    expenses_foreign: Decimal
    withdrawals: Decimal
    withdrawals_foreign: Decimal
    exchange_in: Decimal
    exchange_in_foreign: Decimal
    exchange_out: Decimal
    exchange_out_foreign: Decimal
    adjustments_in: Decimal
    adjustments_in_foreign: Decimal
    adjustments_out: Decimal
    adjustments_out_foreign: Decimal
    expected_local: Decimal
    expected_foreign: Decimal
    expected_cash: Decimal
    counted_cash: Decimal | None
    counted_foreign: Decimal | None
    difference: Decimal | None
    difference_local: Decimal | None
    difference_foreign: Decimal | None
    total_sales: Decimal

    @property
    def carryover_cash(self):
        return self.counted_cash if self.counted_cash is not None else self.expected_cash

    @property
    def carryover_local(self):
        return self.counted_cash if self.counted_cash is not None else self.expected_local

    @property
    def carryover_foreign(self):
        return self.counted_foreign if self.counted_foreign is not None else self.expected_foreign

    @property
    def total_in_local(self):
        return self.owner_deposits + self.exchange_in + self.adjustments_in

    @property
    def total_in_foreign(self):
        return self.owner_deposits_foreign + self.exchange_in_foreign + self.adjustments_in_foreign

    @property
    def cash_day_local(self):
        return self.opening_float

    @property
    def cash_day_foreign(self):
        return self.opening_foreign

    @property
    def total_out_local(self):
        return self.purchases + self.withdrawals + self.exchange_out + self.adjustments_out

    @property
    def total_out_foreign(self):
        return self.purchases_foreign + self.withdrawals_foreign + self.exchange_out_foreign + self.adjustments_out_foreign

    @property
    def net_movement_local(self):
        return self.total_in_local - self.total_out_local

    @property
    def net_movement_foreign(self):
        return self.total_in_foreign - self.total_out_foreign

    @property
    def foreign_variation(self):
        return self.expected_foreign - self.opening_foreign

    @property
    def foreign_variation_fc(self):
        return _money(self.foreign_variation * self.exchange_rate)

    @property
    def sales_balance(self):
        """Net result of today's validated sales after approved expenses."""
        return _money(self.total_sales - self.expenses)

    @property
    def cash_balance_local(self):
        return self.expected_local

    @property
    def cash_balance_foreign(self):
        return self.expected_foreign

    @property
    def cash_balance_fc(self):
        return self.expected_cash

    @property
    def cash_balance_fc_local(self):
        return self.expected_local

    @property
    def cash_balance_usd(self):
        return self.expected_foreign

    @property
    def cash_balance_usd_fc(self):
        return _money(self.expected_foreign * self.exchange_rate)

    @property
    def general_balance_local(self):
        return _money(self.sales_balance + self.expected_local)

    @property
    def general_balance_foreign(self):
        return self.expected_foreign

    @property
    def total_general(self):
        # Les ventes sont en FC ; le solde USD est converti au taux courant
        # avant d'être ajouté au solde général exprimé en FC.
        return _money(self.general_balance_local + self.general_balance_foreign * self.exchange_rate)

    @property
    def counted_total_fc(self):
        if self.counted_cash is None:
            return None
        return _money(self.counted_cash + self.counted_foreign * self.exchange_rate)

    @property
    def general_difference(self):
        """Equivalent FC difference kept for compatibility with old reports."""
        if self.general_difference_local is None:
            return None
        return _money(self.general_difference_local + self.general_difference_foreign * self.exchange_rate)

    @property
    def general_difference_abs(self):
        return _money(abs(self.general_difference)) if self.general_difference is not None else None

    @property
    def general_difference_local(self):
        if self.counted_cash is None:
            return None
        return _money(self.counted_cash - self.general_balance_local)

    @property
    def general_difference_foreign(self):
        if self.counted_foreign is None:
            return None
        return _money(self.counted_foreign - self.general_balance_foreign)

    @property
    def general_difference_local_abs(self):
        return _money(abs(self.general_difference_local)) if self.general_difference_local is not None else None

    @property
    def general_difference_foreign_abs(self):
        return _money(abs(self.general_difference_foreign)) if self.general_difference_foreign is not None else None


def cash_report_for(session: CashSession) -> CashReport:
    movements = session.cash_transactions.filter(voided_at__isnull=True)

    def total(category, direction):
        row = movements.filter(category=category, direction=direction).aggregate(local=Sum("amount"), foreign=Sum("foreign_amount"))
        return _money(row["local"]), _money(row["foreign"])

    opening = total(CashTransaction.Category.OPENING_FLOAT, CashTransaction.Direction.IN)
    deposits = total(CashTransaction.Category.OWNER_DEPOSIT, CashTransaction.Direction.IN)
    purchases = total(CashTransaction.Category.PURCHASE, CashTransaction.Direction.OUT)
    # Les dépenses de vente sont la source Expense approuvée. Elles ne sont
    # jamais déduites des sorties cash opérationnelles.
    # Les dépenses sont rattachées à la session (pas à la date du jour) pour éviter
    # tout écart si une session traverse minuit.
    approved_expense_total = Expense.objects.filter(
        cash_session=session,
        status=Expense.Status.APPROVED,
    ).aggregate(total=Sum("amount"))["total"]
    expenses = (_money(approved_expense_total), ZERO)
    withdrawals = total(CashTransaction.Category.WITHDRAWAL, CashTransaction.Direction.OUT)
    exchange_in = total(CashTransaction.Category.EXCHANGE_IN, CashTransaction.Direction.IN)
    exchange_out = total(CashTransaction.Category.EXCHANGE_OUT, CashTransaction.Direction.OUT)
    adjustment_in = total(CashTransaction.Category.ADJUSTMENT, CashTransaction.Direction.IN)
    adjustment_out = total(CashTransaction.Category.ADJUSTMENT, CashTransaction.Direction.OUT)
    invoices = Invoice.objects.validated().filter(cash_session=session, created_at__date=timezone.localdate())
    cash_sales = _money(Payment.objects.filter(invoice__in=invoices, method=Payment.Method.CASH).aggregate(total=Sum("amount"))["total"])
    total_sales = _money(invoices.aggregate(total=Sum("total"))["total"])
    rate = _money(StoreSettings.get_solo().exchange_rate)
    # Le chiffre des ventes est un rapport séparé : il ne modifie jamais le
    # cash opérationnel FC/USD de la session.
    expected_local = _money(opening[0] + deposits[0] + exchange_in[0] + adjustment_in[0] - purchases[0] - withdrawals[0] - exchange_out[0] - adjustment_out[0])
    expected_foreign = _money(opening[1] + deposits[1] + exchange_in[1] + adjustment_in[1] - purchases[1] - withdrawals[1] - exchange_out[1] - adjustment_out[1])
    expected_cash = _money(expected_local + expected_foreign * rate)
    counted_local = session.counted_local_amount if session.counted_local_amount is not None else session.counted_cash
    counted_foreign = session.counted_foreign_amount if session.counted_foreign_amount is not None else ZERO
    difference = _money(counted_local + counted_foreign * rate - expected_cash) if counted_local is not None else None
    difference_local = _money(counted_local - expected_local) if counted_local is not None else None
    difference_foreign = _money(counted_foreign - expected_foreign) if counted_foreign is not None else None
    return CashReport(
        session=session,
        exchange_rate=rate,
        opening_float=opening[0], opening_foreign=opening[1],
        owner_deposits=deposits[0], owner_deposits_foreign=deposits[1],
        cash_sales=cash_sales, cash_sales_foreign=ZERO,
        purchases=purchases[0], purchases_foreign=purchases[1],
        expenses=expenses[0], expenses_foreign=expenses[1],
        withdrawals=withdrawals[0], withdrawals_foreign=withdrawals[1],
        exchange_in=exchange_in[0], exchange_in_foreign=exchange_in[1],
        exchange_out=exchange_out[0], exchange_out_foreign=exchange_out[1],
        adjustments_in=adjustment_in[0], adjustments_in_foreign=adjustment_in[1],
        adjustments_out=adjustment_out[0], adjustments_out_foreign=adjustment_out[1],
        expected_local=expected_local, expected_foreign=expected_foreign, expected_cash=expected_cash,
        counted_cash=counted_local, counted_foreign=counted_foreign,
        difference=difference, difference_local=difference_local, difference_foreign=difference_foreign,
        total_sales=total_sales,
    )
