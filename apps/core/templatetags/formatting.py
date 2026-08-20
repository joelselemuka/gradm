from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django import template


register = template.Library()


@register.filter
def money(value):
    """Format amounts with a dot thousands separator and two decimals."""
    if value in (None, ""):
        return "0,00"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", ".")
    formatted = f"{amount:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter(name="floatformat")
def floatformat_money(value, precision=None):
    """Group thousands while keeping useful decimals on small amounts."""
    if value in (None, ""):
        return "0,00"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if amount == amount.to_integral() and abs(amount) < 1000 and str(precision or "2") != "0":
        formatted = f"{amount:,.2f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return money(amount)
