from .models import AuditLog


def audit(*, actor, action: str, target, before=None, after=None):
    return AuditLog.objects.create(actor=actor, action=action, target_type=target._meta.label, target_id=str(target.pk), before=before or {}, after=after or {})
