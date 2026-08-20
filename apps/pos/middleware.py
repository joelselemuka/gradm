from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login

from .models import CashSession


class OpenCashSessionRequiredMiddleware:
    """Require an open cashier session before entering the operational POS.

    Authentication alone is not enough to authorize a cashier to sell.  The
    session is deliberately looked up from the database on every request so
    that closing a session immediately revokes access, including for direct
    POST/HTMX requests that bypass the POS page.

    Administrators keep access to the read-only sales supervision view; they
    do not use the operational cart and therefore do not need a cashier
    session.  Operational roles (cashier/manager) must own an OPEN session.
    The view-level ``_require_active_session`` check remains as defence in
    depth for non-HTTP callers and future routes.
    """

    POS_PREFIX = "/sales/pos/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requires_open_session(request):
            has_open_session = CashSession.objects.filter(
                cashier_id=request.user.pk,
                status=CashSession.Status.OPEN,
            ).exists()
            if not has_open_session:
                # An authenticated cashier without an open session must not
                # remain connected with a stale POS context.  End the Django
                # session first, then send them through the normal login flow.
                logout(request)
                return redirect_to_login(
                    request.get_full_path(),
                    login_url="/users/login/",
                )
        return self.get_response(request)

    def _requires_open_session(self, request):
        if not request.path_info.startswith(self.POS_PREFIX):
            return False
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        # ADMIN uses /sales/pos/ as a read-only sales overview and never
        # operates a cart.  Only roles allowed to encash are session-bound.
        return request.user.can_operate_pos()
