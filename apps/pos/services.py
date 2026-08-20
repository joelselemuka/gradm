from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import audit
from apps.core.models import StoreSettings
from apps.pos.models import CashSession, CashTransaction
from apps.pos.selectors import cash_report_for
from apps.sales.models import Invoice, Payment


ZERO = Decimal("0.00")


def _decimal(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _display_amount(value):
    """Format a monetary value for a clear message shown to the cashier."""
    value = _decimal(value)
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


class CashSessionService:
    @staticmethod
    @transaction.atomic
    def open_session(*, register, actor, opening_amount=None, opening_local_amount=None, opening_foreign_amount=ZERO, cashier=None):
        if not (actor.can_operate_pos() or actor.can_manage_cash()):
            raise PermissionDenied("Utilisateur non autorisé à ouvrir une caisse.")
        cashier = cashier or actor
        if not cashier.can_operate_pos():
            raise ValidationError("Le caissier sélectionné ne peut pas exploiter le point de vente.")
        if cashier.pk != actor.pk and not actor.can_manage_cash():
            raise PermissionDenied("Seul un administrateur peut ouvrir une caisse pour un autre caissier.")
        if opening_local_amount is None:
            opening_local_amount = opening_amount if opening_amount is not None else ZERO
        local = _decimal(opening_local_amount)
        foreign = _decimal(opening_foreign_amount)
        if local < 0 or foreign < 0:
            raise ValidationError("Les fonds initiaux ne peuvent pas être négatifs.")
        if (local or foreign) and not actor.can_manage_cash():
            raise PermissionDenied("Seul un administrateur peut remettre un fonds initial.")
        if not register.active:
            raise ValidationError("Cette caisse est désactivée.")
        if CashSession.objects.select_for_update().filter(register=register, status=CashSession.Status.OPEN).exists():
            raise ValidationError("Cette caisse a déjà une session ouverte.")
        if CashSession.objects.select_for_update().filter(cashier=cashier, status=CashSession.Status.OPEN).exists():
            raise ValidationError("Ce caissier a déjà une session ouverte.")
        try:
            with transaction.atomic():
                session = CashSession.objects.create(
                    register=register,
                    cashier=cashier,
                    opening_amount=local,
                    opening_local_amount=local,
                    opening_foreign_amount=foreign,
                )
        except IntegrityError as exc:
            raise ValidationError("La caisse ou le caissier possède déjà une session ouverte.") from exc
        if local or foreign:
            CashTransaction.objects.create(
                session=session,
                direction=CashTransaction.Direction.IN,
                category=CashTransaction.Category.OPENING_FLOAT,
                amount=local,
                foreign_amount=foreign or None,
                foreign_currency="USD" if foreign else "",
                exchange_rate=_decimal(StoreSettings.get_solo().exchange_rate) if foreign else None,
                description="Fonds de caisse à l'ouverture",
                created_by=actor,
            )
        audit(actor=actor, action="CASH_SESSION_OPENED", target=session, after={"opening_local_amount": str(local), "opening_foreign_amount": str(foreign), "cashier_id": cashier.pk})
        return session

    @staticmethod
    def _can_operate_session(session, actor):
        return actor.can_manage_cash() or session.cashier_id == actor.pk

    @staticmethod
    def _available_balances(session):
        """Return the spendable FC/USD balances for the open session.

        Sales expenses deliberately stay in their own reporting section, but
        an approved expense still consumes physical cash.  We therefore keep
        it out of the cash movement totals while subtracting it from the
        amount that can safely be spent.
        """
        report = cash_report_for(session)
        return (
            max(report.expected_local - report.expenses, ZERO),
            max(report.expected_foreign, ZERO),
        )

    @staticmethod
    def _available_sales_balance(session):
        """Return the FC still available for expenses from today's sales."""
        return max(cash_report_for(session).sales_balance, ZERO)

    @staticmethod
    def ensure_expense_available(*, session, amount):
        """Reject a cash-expense request before it enters the approval queue."""
        amount = _decimal(amount)
        available_local = CashSessionService._available_sales_balance(session)
        if amount > available_local:
            raise ValidationError(
                "Demande refusée : la dépense de "
                f"{_display_amount(amount)} FC n’a pas été envoyée, car elle est "
                f"supérieure au solde disponible de cette caisse ({_display_amount(available_local)} FC). "
                "Saisissez un montant inférieur ou égal au solde actuel."
            )

    @staticmethod
    def _ensure_available(*, session, local, foreign, local_available=None, foreign_available=None):
        local_available = local_available if local_available is not None else CashSessionService._available_balances(session)[0]
        foreign_available = foreign_available if foreign_available is not None else CashSessionService._available_balances(session)[1]
        if local > local_available:
            raise ValidationError(
                "Opération refusée : la sortie de "
                f"{_display_amount(local)} FC n’a pas été enregistrée, car elle est "
                f"supérieure au solde disponible de cette caisse ({_display_amount(local_available)} FC). "
                "Saisissez un montant inférieur ou égal au solde actuel."
            )
        if foreign > foreign_available:
            raise ValidationError(
                "Opération refusée : la sortie de "
                f"{_display_amount(foreign)} USD n’a pas été enregistrée, car elle est "
                f"supérieure au solde disponible de cette caisse ({_display_amount(foreign_available)} USD). "
                "Saisissez un montant inférieur ou égal au solde actuel."
            )

    @staticmethod
    @transaction.atomic
    def record_movement(*, session: CashSession, actor, direction: str, category: str = None, label: str = "", amount=None, local_amount=None, foreign_amount=None, description: str, reference: str = ""):
        legacy_amount_call = amount is not None and local_amount is None and foreign_amount is None
        local = _decimal(local_amount if local_amount is not None else amount)
        foreign = _decimal(foreign_amount)
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        if not CashSessionService._can_operate_session(session, actor) or (legacy_amount_call and not actor.can_manage_cash()):
            raise PermissionDenied("Cette opération est réservée au caissier de la session ou à un administrateur.")
        if session.status != CashSession.Status.OPEN:
            raise ValidationError("Impossible de modifier une caisse clôturée.")
        label = (label or description or "").strip()
        if local <= 0 and foreign <= 0 or not description.strip() or not label:
            raise ValidationError("Saisissez un montant positif en FC, en USD, ou les deux, avec un libellé et un motif obligatoires.")
        permitted = {
            CashTransaction.Category.OWNER_DEPOSIT: CashTransaction.Direction.IN,
            CashTransaction.Category.PURCHASE: CashTransaction.Direction.OUT,
            CashTransaction.Category.EXPENSE: CashTransaction.Direction.OUT,
            CashTransaction.Category.WITHDRAWAL: CashTransaction.Direction.OUT,
            CashTransaction.Category.ADJUSTMENT: direction,
        }
        if direction not in CashTransaction.Direction.values or category not in permitted or permitted[category] != direction:
            raise ValidationError("Type de mouvement de caisse invalide.")
        if direction == CashTransaction.Direction.OUT:
            if category == CashTransaction.Category.EXPENSE:
                if foreign > 0:
                    raise ValidationError("Les dépenses sont enregistrées en FC uniquement.")
                CashSessionService.ensure_expense_available(session=session, amount=local)
            else:
                available_local, available_foreign = CashSessionService._available_balances(session)
                CashSessionService._ensure_available(
                    session=session,
                    local=local,
                    foreign=foreign,
                    local_available=available_local,
                    foreign_available=available_foreign,
                )
        rate = _decimal(StoreSettings.get_solo().exchange_rate) if foreign else None
        movement = CashTransaction.objects.create(
            session=session,
            direction=direction,
            category=category,
            label=label[:120],
            amount=local,
            foreign_amount=foreign or None,
            foreign_currency="USD" if foreign else "",
            exchange_rate=rate,
            description=description.strip(),
            reference=reference.strip(),
            created_by=actor,
        )
        audit(actor=actor, action="CASH_MOVEMENT_RECORDED", target=movement, after={"direction": direction, "category": category, "label": label, "local_amount": str(local), "foreign_amount": str(foreign)})
        return movement

    @staticmethod
    @transaction.atomic
    def record_currency_exchange(*, session: CashSession, actor, foreign_amount: Decimal = None, local_out: Decimal = None, foreign_in: Decimal = None, description: str = ""):
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        if not CashSessionService._can_operate_session(session, actor):
            raise PermissionDenied("Cette opération est réservée au caissier de la session ou à un administrateur.")
        if session.status != CashSession.Status.OPEN:
            raise ValidationError("Impossible de modifier une caisse clôturée.")
        # ``local_out``/``foreign_in`` are accepted for old integrations; the
        # FC amount is now always derived from the USD amount and the current rate.
        foreign = _decimal(foreign_amount if foreign_amount is not None else foreign_in)
        rate = _decimal(StoreSettings.get_solo().exchange_rate)
        local = _decimal(foreign * rate)
        description = (description or "Change USD vers FC").strip()
        if local <= 0 or foreign <= 0:
            raise ValidationError("Le montant USD du change doit être positif.")
        available_local, _ = CashSessionService._available_balances(session)
        CashSessionService._ensure_available(
            session=session,
            local=local,
            foreign=ZERO,
            local_available=available_local,
            foreign_available=ZERO,
        )
        group_id = uuid4()
        out = CashTransaction.objects.create(session=session, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.EXCHANGE_OUT, amount=local, description=description.strip(), foreign_currency="USD", exchange_rate=rate, group_id=group_id, created_by=actor)
        incoming = CashTransaction.objects.create(session=session, direction=CashTransaction.Direction.IN, category=CashTransaction.Category.EXCHANGE_IN, amount=ZERO, foreign_amount=foreign, description=description.strip(), foreign_currency="USD", exchange_rate=rate, group_id=group_id, created_by=actor)
        audit(actor=actor, action="CASH_EXCHANGE_RECORDED", target=out, after={"local_out": str(local), "foreign_in": str(foreign), "rate": str(rate)})
        return out, incoming

    @staticmethod
    @transaction.atomic
    def record_exchange(*, session: CashSession, actor, cash_out: Decimal, cash_in: Decimal, foreign_currency: str, foreign_amount: Decimal, description: str):
        """Backward-compatible API for legacy integrations.

        New UI operations use ``record_currency_exchange`` so FC out and USD
        in are kept in separate currency columns.
        """
        return CashSessionService.record_movement_pair_legacy(session=session, actor=actor, cash_out=cash_out, cash_in=cash_in, foreign_currency=foreign_currency, foreign_amount=foreign_amount, description=description)

    @staticmethod
    @transaction.atomic
    def record_movement_pair_legacy(*, session, actor, cash_out, cash_in, foreign_currency, foreign_amount, description):
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        if not CashSessionService._can_operate_session(session, actor):
            raise PermissionDenied("Cette opération est réservée au caissier de la session ou à un administrateur.")
        if session.status != CashSession.Status.OPEN:
            raise ValidationError("Impossible de modifier une caisse clôturée.")
        if min(_decimal(cash_out), _decimal(cash_in), _decimal(foreign_amount)) <= 0 or foreign_currency.upper().strip() != "USD" or not description.strip():
            raise ValidationError("Les montants, la devise et le motif du change sont obligatoires.")
        # In the legacy exchange API the FC received from the customer is
        # available immediately for the FC handed back in the same atomic
        # operation.  It is therefore safe to compare the outgoing amount to
        # the current balance plus that incoming amount.
        available_local, available_foreign = CashSessionService._available_balances(session)
        CashSessionService._ensure_available(
            session=session,
            local=_decimal(cash_out),
            # ``foreign_amount`` is the USD received from the customer in
            # this legacy exchange shape, not USD handed out.
            foreign=ZERO,
            local_available=available_local + _decimal(cash_in),
            foreign_available=available_foreign,
        )
        rate = _decimal(StoreSettings.get_solo().exchange_rate)
        group_id = uuid4()
        out = CashTransaction.objects.create(session=session, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.EXCHANGE_OUT, amount=_decimal(cash_out), foreign_amount=_decimal(foreign_amount), description=description.strip(), foreign_currency="USD", exchange_rate=rate, group_id=group_id, created_by=actor)
        incoming = CashTransaction.objects.create(session=session, direction=CashTransaction.Direction.IN, category=CashTransaction.Category.EXCHANGE_IN, amount=_decimal(cash_in), foreign_amount=_decimal(foreign_amount), description=description.strip(), foreign_currency="USD", exchange_rate=rate, group_id=group_id, created_by=actor)
        audit(actor=actor, action="CASH_EXCHANGE_RECORDED", target=out, after={"cash_out": str(cash_out), "cash_in": str(cash_in), "currency": "USD"})
        return out, incoming

    @staticmethod
    @transaction.atomic
    def void_movement(*, movement: CashTransaction, actor, reason: str):
        if not actor.can_manage_cash():
            raise PermissionDenied("Seul un administrateur peut annuler un mouvement de caisse.")
        if not reason.strip():
            raise ValidationError("Un motif d'annulation est obligatoire.")
        movement = CashTransaction.objects.select_for_update().select_related("session").get(pk=movement.pk)
        if movement.session.status != CashSession.Status.OPEN:
            raise ValidationError("Un mouvement d'une caisse clôturée ne peut pas être annulé.")
        if movement.voided_at:
            raise ValidationError("Ce mouvement est déjà annulé.")
        movements = CashTransaction.objects.select_for_update().filter(group_id=movement.group_id, voided_at__isnull=True)
        movements.update(voided_at=timezone.now(), voided_by=actor, void_reason=reason.strip())
        audit(actor=actor, action="CASH_MOVEMENT_VOIDED", target=movement, after={"reason": reason.strip()})

    @staticmethod
    @transaction.atomic
    def close_session(*, session: CashSession, actor, counted_cash=None, counted_local_amount=None, counted_foreign_amount=ZERO, sales_deposit_local_amount=None, sales_deposit_foreign_amount=None):
        session = CashSession.objects.select_for_update().get(pk=session.pk)
        if session.cashier_id != actor.pk and not actor.can_cancel_invoice():
            raise PermissionDenied("Vous ne pouvez pas clôturer cette caisse.")
        if session.status != CashSession.Status.OPEN:
            raise ValidationError("La session est déjà fermée.")
        local = _decimal(counted_local_amount if counted_local_amount is not None else counted_cash)
        foreign = _decimal(counted_foreign_amount)
        report = cash_report_for(session)
        # Legacy callers that did not yet send the two sales fields are
        # treated as having deposited the complete sales total in FC. The
        # HTTP form still requires both fields explicitly (see the view).
        if sales_deposit_local_amount is None and sales_deposit_foreign_amount is None:
            sales_local = report.total_sales
            sales_foreign = ZERO
        else:
            sales_local = _decimal(sales_deposit_local_amount)
            sales_foreign = _decimal(sales_deposit_foreign_amount)
        if local < 0 or foreign < 0 or sales_local < 0 or sales_foreign < 0:
            raise ValidationError("Les montants comptés ne peuvent pas être négatifs.")
        expected = report.expected_cash
        counted_total = local + foreign * report.exchange_rate
        difference = counted_total - expected
        sales_deposit_total = sales_local + sales_foreign * report.exchange_rate
        sales_difference = sales_deposit_total - report.total_sales
        session.status = CashSession.Status.CLOSED
        session.expected_cash = expected
        session.expected_sales = report.total_sales
        session.sales_deposit_local_amount = sales_local
        session.sales_deposit_foreign_amount = sales_foreign
        session.sales_difference = sales_difference
        session.expected_local_amount = report.expected_local
        session.expected_foreign_amount = report.expected_foreign
        session.counted_cash = local
        session.counted_local_amount = local
        session.counted_foreign_amount = foreign
        session.difference = difference
        session.difference_local_amount = local - report.expected_local
        session.difference_foreign_amount = foreign - report.expected_foreign
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "expected_cash", "expected_sales", "sales_deposit_local_amount", "sales_deposit_foreign_amount", "sales_difference", "expected_local_amount", "expected_foreign_amount", "counted_cash", "counted_local_amount", "counted_foreign_amount", "difference", "difference_local_amount", "difference_foreign_amount", "closed_at"])
        audit(actor=actor, action="CASH_SESSION_CLOSED", target=session, after={"difference": str(difference), "counted_local": str(local), "counted_foreign": str(foreign), "sales_difference": str(sales_difference), "sales_deposit_local": str(sales_local), "sales_deposit_foreign": str(sales_foreign)})

        # ── Calcul du solde de versement ──────────────────────────────────────
        # Solde général (FC + USD converti) - Total versement (FC + USD converti)
        rate = report.exchange_rate
        solde_general_fc  = _decimal(report.sales_balance + report.expected_local)
        solde_general_usd = report.expected_foreign
        total_versement_fc  = _decimal(sales_local + local)
        total_versement_usd = _decimal(sales_foreign + foreign)
        solde_general_eq  = _decimal(solde_general_fc  + solde_general_usd  * rate)
        versement_eq      = _decimal(total_versement_fc + total_versement_usd * rate)
        deposit_diff_fc   = _decimal(solde_general_eq - versement_eq)
        # On stocke la différence en FC (équivalent) et le surplus USD brut.
        session.deposit_balance_local   = deposit_diff_fc
        session.deposit_balance_foreign = _decimal(solde_general_usd - total_versement_usd)
        session.save(update_fields=["deposit_balance_local", "deposit_balance_foreign"])

        # ── Génération du PDF de clôture ──────────────────────────────────────
        try:
            from apps.reports.pdf import generate_session_pdf
            from apps.expenses.models import Expense
            from django.core.files.base import ContentFile
            session_expenses = Expense.objects.filter(
                cash_session=session,
                status=Expense.Status.APPROVED,
            ).order_by("created_at")
            pdf_bytes = generate_session_pdf(
                session=session,
                report=report,
                expenses=session_expenses,
                rate=rate,
            )
            filename = f"rapport_session_{session.pk}_{session.closed_at.strftime('%Y%m%d_%H%M')}.pdf"
            session.report_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        except Exception:
            logger.exception("Impossible de générer le PDF pour la session %s", session.pk)
            pdf_bytes = None

        # ── Notifications internes ────────────────────────────────────────────
        from apps.accounts.models import User
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        summary = f"Session {session.register.name} clôturée : ventes {report.total_sales}, sorties FC {report.total_out_local}, sorties USD {report.total_out_foreign}, solde FC équivalent {expected}."
        admins = User.objects.filter(is_active=True, role=User.Role.ADMIN)
        for admin in admins:
            notify(recipient=admin, level=Notification.Level.INFO, title="Rapport de cash clôturé", message=summary, target_url=f"/cash/sessions/{session.pk}/")

        # ── Email de clôture avec PDF en pièce jointe ─────────────────────────
        from apps.reports.services import report_recipient
        from django.core.mail import EmailMessage
        recipient = report_recipient()
        if recipient:
            try:
                mail = EmailMessage(
                    subject=f"[GSM] Rapport de clôture — Session #{session.pk} — {session.register.name}",
                    body=summary,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                )
                if pdf_bytes:
                    mail.attach(filename, pdf_bytes, "application/pdf")
                mail.send(fail_silently=True)
            except Exception:
                logger.exception("Impossible d'envoyer l'email de clôture pour la session %s", session.pk)

        # ── Rapport général (dernière session de la journée) ──────────────────
        opened_day = timezone.localtime(session.opened_at).date()
        other_open_session = CashSession.objects.filter(
            opened_at__date=opened_day,
            status=CashSession.Status.OPEN,
        ).exists()
        if not other_open_session:
            from apps.reports.services import send_general_report
            transaction.on_commit(
                lambda day=opened_day: send_general_report(day=day, fail_silently=True)
            )
        return session

