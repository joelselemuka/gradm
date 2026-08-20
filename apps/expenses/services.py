from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from apps.audit.services import audit
from apps.pos.models import CashSession
from .models import Expense


class ExpenseService:
    @staticmethod
    @transaction.atomic
    def submit(*, actor, category, amount, description):
        if actor.role != actor.Role.CASHIER:
            raise PermissionDenied("Seul un caissier peut soumettre une dépense.")
        if not description.strip():
            raise ValidationError("Le motif de la dépense est obligatoire.")
        cash_session = CashSession.objects.select_for_update().filter(cashier=actor, status=CashSession.Status.OPEN).select_related("register").first()
        if not cash_session:
            raise ValidationError("La dépense doit être rattachée à votre session de vente ouverte.")
        from apps.pos.services import CashSessionService
        CashSessionService.ensure_expense_available(session=cash_session, amount=amount)
        expense = Expense.objects.create(category=category.strip(), amount=amount, description=description.strip(), expense_date=timezone.localdate(), requester=actor, paid_in_cash=True, cash_session=cash_session)
        from apps.accounts.models import User
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        for admin in User.objects.filter(is_active=True, role=User.Role.ADMIN):
            notify(recipient=admin, level=Notification.Level.WARNING, title="Dépense à approuver", message=f"{actor.username} a soumis {expense.amount} : {expense.description[:90]}", target_url=reverse("expenses:detail", kwargs={"pk": expense.pk}))
        audit(actor=actor, action="EXPENSE_SUBMITTED", target=expense, after={"amount": str(amount)})
        return expense

    @staticmethod
    @transaction.atomic
    def approve(*, expense, actor, comment=""):
        if not actor.can_approve_expense(): raise PermissionDenied("Seul ADMIN peut approuver une dépense.")
        expense = Expense.objects.select_for_update().get(pk=expense.pk)
        if expense.status != Expense.Status.PENDING: raise ValidationError("Cette dépense a déjà été traitée.")
        if expense.paid_in_cash:
            if not expense.cash_session: raise ValidationError("Une session de caisse est requise.")
            from apps.pos.models import CashTransaction
            from apps.pos.services import CashSessionService
            CashSessionService.record_movement(session=expense.cash_session, actor=actor, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.EXPENSE, amount=expense.amount, description=expense.description[:300], reference=f"DEP-{expense.pk}")
        expense.status=Expense.Status.APPROVED; expense.approved_by=actor; expense.approval_comment=comment; expense.decided_at=timezone.now(); expense.save(update_fields=["status","approved_by","approval_comment","decided_at"])
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        notify(recipient=expense.requester, level=Notification.Level.INFO, title="Dépense approuvée", message=f"La dépense {expense.category} a été approuvée.", target_url=reverse("expenses:detail", kwargs={"pk": expense.pk}))
        audit(actor=actor,action="EXPENSE_APPROVED",target=expense,after={"amount":str(expense.amount)})
        return expense

    @staticmethod
    @transaction.atomic
    def reject(*, expense, actor, comment):
        if not actor.can_approve_expense(): raise PermissionDenied("Seul ADMIN peut refuser une dépense.")
        if not comment.strip(): raise ValidationError("Le motif du refus est obligatoire.")
        expense=Expense.objects.select_for_update().get(pk=expense.pk)
        if expense.status != Expense.Status.PENDING: raise ValidationError("Cette dépense a déjà été traitée.")
        expense.status=Expense.Status.REJECTED; expense.approved_by=actor; expense.approval_comment=comment; expense.decided_at=timezone.now(); expense.save(update_fields=["status","approved_by","approval_comment","decided_at"])
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        notify(recipient=expense.requester, level=Notification.Level.WARNING, title="Dépense refusée", message=f"La dépense {expense.category} a été refusée.", target_url=reverse("expenses:detail", kwargs={"pk": expense.pk}))
        audit(actor=actor,action="EXPENSE_REJECTED",target=expense,after={"reason":comment}); return expense
