"""Shared, server-side date range parsing for reporting dashboards."""

from calendar import monthrange
from datetime import date, timedelta

from django.utils import timezone


PERIOD_CHOICES = {
    "day": "Jour",
    "week": "Semaine",
    "month": "Mois",
    "year": "Année",
    "custom": "Intervalle personnalisé",
}


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def get_date_range(params):
    """Return a normalized range from GET/POST-like params.

    The anchor date makes week/month/year filters predictable when a date is
    supplied. Invalid values safely fall back to the current local day.
    """

    today = timezone.localdate()
    period = str(params.get("period") or "day").lower()
    if period not in PERIOD_CHOICES:
        period = "day"
    anchor = _parse_date(params.get("date")) or today

    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = anchor.replace(day=1)
        end = anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
    elif period == "year":
        start = anchor.replace(month=1, day=1)
        end = anchor.replace(month=12, day=31)
    elif period == "custom":
        start = _parse_date(params.get("date_from")) or anchor
        end = _parse_date(params.get("date_to")) or start
    else:
        start = end = anchor

    if start > end:
        start, end = end, start

    return {
        "period": period,
        "period_label": PERIOD_CHOICES[period],
        "start": start,
        "end": end,
        "selected_date": anchor,
        "date_from": start if period == "custom" else "",
        "date_to": end if period == "custom" else "",
        "days": (end - start).days + 1,
    }
