from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.notifications.models import Notification
from apps.notifications.services import notify
from .alerts import expired_rows, expiring_rows, low_stock_rows


def scan_expiration_alerts():
    """Create one idempotent alert per day for expired and soon-expiring lots."""
    today = timezone.localdate()
    expired = expired_rows(today)
    expiring = expiring_rows(today)
    low_stock = low_stock_rows()
    # Older per-variant replenishment alerts remain actionable after the new
    # consolidated alert/list was introduced.
    Notification.objects.filter(title="Réapprovisionnement requis", target_url="").update(target_url="/inventory/alerts/low-stock/")
    recipients = get_user_model().objects.filter(role="ADMIN", is_active=True)
    low_stock_recipients = get_user_model().objects.filter(role__in=["ADMIN", "MANAGER"], is_active=True)
    created = 0
    alerts = []
    expired_count = len(expired)
    expiring_count = len(expiring)
    if expired_count:
        alerts.append(("Produits expirés", f"{expired_count} produit(s) expiré(s) nécessitent une action.", "/inventory/alerts/expired/", recipients))
    if expiring_count:
        alerts.append(("Produits bientôt expirés", f"{expiring_count} produit(s) arrivent à expiration dans les 60 jours.", "/inventory/alerts/expiring/", recipients))
    if low_stock:
        alerts.append(("Stock faible", f"{len(low_stock)} produit(s) ont atteint leur seuil de stock.", "/inventory/alerts/low-stock/", low_stock_recipients))
    for title, message, target_url, alert_recipients in alerts:
        for user in alert_recipients:
            existing = Notification.objects.filter(recipient=user, title=title).order_by("-created_at").first()
            if existing:
                if existing.message != message or existing.target_url != target_url:
                    existing.message = message
                    existing.target_url = target_url
                    existing.save(update_fields=["message", "target_url"])
                if existing.created_at.date() == today:
                    continue
                # Keep an older unread alert useful by updating it in place;
                # otherwise create a fresh daily notification.
                if not existing.read_at:
                    continue
            notify(recipient=user, level=Notification.Level.WARNING, title=title, message=message, target_url=target_url)
            created += 1
    return created


@shared_task
def notify_expiring_lots():
    return scan_expiration_alerts()
