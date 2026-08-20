from apps.pos.models import CashSession


def navigation(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notification_count": 0, "active_cash_session": None}
    active_cash_session = CashSession.objects.filter(
        cashier=request.user,
        status=CashSession.Status.OPEN,
    ).select_related("register").first()
    return {
        "unread_notification_count": request.user.notifications.filter(read_at__isnull=True).count(),
        "active_cash_session": active_cash_session,
    }
