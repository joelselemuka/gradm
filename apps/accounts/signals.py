import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from apps.audit.services import audit

logger = logging.getLogger("django.security")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Enregistre chaque connexion réussie dans l'audit log."""
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "?"))
    audit(
        actor=user,
        action="USER_LOGGED_IN",
        target=user,
        after={"ip": ip, "username": user.username},
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Enregistre chaque déconnexion dans l'audit log."""
    if user:
        audit(actor=user, action="USER_LOGGED_OUT", target=user)


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    """Logue les tentatives de connexion échouées (détection brute force)."""
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "?"))
    logger.warning(
        "Tentative de connexion échouée pour '%s' depuis %s",
        credentials.get("username", "?"),
        ip,
    )
