from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Sum
from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.products.models import ProductVariant
from .models import ReplenishmentNeed


class ReplenishmentService:
    @staticmethod
    @transaction.atomic
    def evaluate_variant(*, variant: ProductVariant):
        """Create one actionable need when available stock reaches its alert threshold."""
        available = variant.lots.aggregate(total=Sum("quantity_available"))["total"] or 0
        threshold = variant.low_stock_threshold
        if available > threshold:
            ReplenishmentNeed.objects.filter(variant=variant, status=ReplenishmentNeed.Status.OPEN).update(status=ReplenishmentNeed.Status.RESOLVED)
            return None
        try:
            need, created = ReplenishmentNeed.objects.get_or_create(
                variant=variant,
                status=ReplenishmentNeed.Status.OPEN,
                defaults={
                    "threshold_snapshot": threshold,
                    "available_snapshot": available,
                    "suggested_quantity": max(threshold * 2 - available, 1),
                },
            )
        except IntegrityError:
            need = ReplenishmentNeed.objects.get(variant=variant, status=ReplenishmentNeed.Status.OPEN)
            created = False
        if not created:
            need.threshold_snapshot = threshold
            need.available_snapshot = available
            need.suggested_quantity = max(threshold * 2 - available, 1)
            need.save(update_fields=["threshold_snapshot", "available_snapshot", "suggested_quantity", "updated_at"])
            return need
        recipients = User.objects.filter(is_active=True, role__in=[User.Role.ADMIN, User.Role.MANAGER])
        title = "Réapprovisionnement requis"
        message = f"{variant.product.name} — {variant.name} : stock {available}, seuil {threshold}."
        for recipient in recipients:
            notify(recipient=recipient, level=Notification.Level.WARNING, title=title, message=message, target_url=f"/inventory/alerts/low-stock/?variant={variant.pk}")
        emails = [email for email in recipients.values_list("email", flat=True) if email]
        if emails:
            send_mail(title, message, None, emails, fail_silently=True)
        return need
