from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib.auth import get_user_model
from apps.core.models import StoreSettings
from .forms import CashExchangeForm, CashMovementForm, CashRegisterForm, CashSessionCloseForm, CashSessionOpenForm, VoidCashMovementForm
from .models import CashRegister, CashSession, CashTransaction
from .selectors import cash_report_for
from .services import CashSessionService



def _accessible_session(request, pk):
    session = get_object_or_404(CashSession.objects.select_related("register", "cashier"), pk=pk)
    if session.cashier_id != request.user.pk and not request.user.can_manage_cash():
        raise PermissionDenied("Vous ne pouvez pas consulter cette caisse.")
    if session.status != CashSession.Status.OPEN and not request.user.can_manage_cash():
        raise PermissionDenied("Cette session est clôturée et n'est plus accessible au caissier.")
    return session


@login_required
def cash_home(request):
    is_admin = request.user.can_manage_cash()
    sessions = CashSession.objects.select_related("register", "cashier")
    selected_date = request.GET.get("date", "")
    selected_cashier = request.GET.get("cashier", "")
    selected_session = request.GET.get("session", "")
    if is_admin:
        if parse_date(selected_date):
            sessions = sessions.filter(opened_at__date=selected_date)
        if selected_cashier.isdigit():
            sessions = sessions.filter(cashier_id=selected_cashier)
        if selected_session.isdigit():
            sessions = sessions.filter(pk=selected_session)
    else:
        sessions = sessions.filter(cashier=request.user)
    sessions = sessions.order_by("-opened_at")
    session = sessions.filter(status=CashSession.Status.OPEN).first()
    if session is None and is_admin:
        session = sessions.first()
    cash_transactions = CashTransaction.objects.filter(session__in=sessions).select_related("created_by", "session__register", "session__cashier").exclude(category=CashTransaction.Category.EXPENSE)
    if not is_admin and session:
        cash_transactions = cash_transactions.filter(session=session)
    cash_transactions = Paginator(cash_transactions, 20).get_page(request.GET.get("page"))
    session_reports = [{"session": item, "report": cash_report_for(item)} for item in sessions[:30]]
    return render(request, "pos/cash_home.html", {
        "is_admin_view": is_admin,
        "session": session,
        "report": cash_report_for(session) if session else None,
        "session_reports": session_reports,
        "cash_transactions": cash_transactions,
        "cashiers": get_user_model().objects.filter(role__in=[get_user_model().Role.CASHIER, get_user_model().Role.MANAGER], is_active=True).order_by("username") if is_admin else [],
        "session_choices": sessions[:100] if is_admin else [],
        "selected_date": selected_date,
        "selected_cashier": selected_cashier,
        "selected_session": selected_session,
        "open_form": CashSessionOpenForm(actor=request.user),
        "register_form": CashRegisterForm(),
        "movement_form": CashMovementForm(),
        "entry_form": CashMovementForm(direction=CashTransaction.Direction.IN),
        "exit_form": CashMovementForm(direction=CashTransaction.Direction.OUT),
        "exchange_form": CashExchangeForm(),
        "store_settings": StoreSettings.get_solo(),
    })


@login_required
def cash_sessions(request):
    if not request.user.can_manage_cash():
        raise PermissionDenied("La gestion des caisses et sessions est réservée à ADMIN.")
    sessions = CashSession.objects.select_related("register", "cashier").order_by("-opened_at")
    selected_date = request.GET.get("date", "")
    selected_cashier = request.GET.get("cashier", "")
    selected_status = request.GET.get("status", "")
    if parse_date(selected_date):
        sessions = sessions.filter(opened_at__date=selected_date)
    if selected_cashier.isdigit():
        sessions = sessions.filter(cashier_id=selected_cashier)
    if selected_status in {CashSession.Status.OPEN, CashSession.Status.CLOSED}:
        sessions = sessions.filter(status=selected_status)
    import json as _json
    # Solde précédent par caisse : {register_id: {local, foreign}}
    prev_balances = {}
    for reg in CashRegister.objects.filter(active=True):
        last = (
            CashSession.objects
            .filter(register=reg, status=CashSession.Status.CLOSED)
            .order_by("-closed_at")
            .values("deposit_balance_local", "deposit_balance_foreign")
            .first()
        )
        if last and last["deposit_balance_local"] is not None:
            prev_balances[str(reg.pk)] = {
                "local":   float(last["deposit_balance_local"] or 0),
                "foreign": float(last["deposit_balance_foreign"] or 0),
            }
    return render(request, "pos/cash_sessions.html", {
        "sessions": Paginator(sessions, 20).get_page(request.GET.get("page")),
        "registers": CashRegister.objects.annotate(open_sessions=Count("sessions", filter=Q(sessions__status=CashSession.Status.OPEN))).order_by("name"),
        "cashiers": get_user_model().objects.filter(role__in=[get_user_model().Role.CASHIER, get_user_model().Role.MANAGER], is_active=True).order_by("username"),
        "selected_date": selected_date,
        "selected_cashier": selected_cashier,
        "selected_status": selected_status,
        "open_form": CashSessionOpenForm(actor=request.user),
        "register_form": CashRegisterForm(),
        "prev_balances_json": _json.dumps(prev_balances),
    })



@login_required
def open_cash_session(request):
    if request.method != "POST": raise Http404
    form = CashSessionOpenForm(request.POST, actor=request.user)
    if not form.is_valid():
        messages.error(request, "Veuillez corriger les informations d'ouverture.")
        return redirect("pos:cash-home")
    try:
        # opening_local et opening_foreign viennent des champs du formulaire
        # (pré-remplis par Alpine côté client si le toggle était coché).
        # On s'assure qu'ils ne sont pas None.
        from decimal import Decimal
        opening_local   = form.cleaned_data.get("opening_local_amount")  or Decimal("0")
        opening_foreign = form.cleaned_data.get("opening_foreign_amount") or Decimal("0")

        CashSessionService.open_session(
            register=form.cleaned_data["register"],
            actor=request.user,
            cashier=form.cleaned_data["cashier"],
            opening_local_amount=opening_local,
            opening_foreign_amount=opening_foreign,
        )
        messages.success(request, "Caisse ouverte.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("pos:cash-home")




@login_required
def create_cash_register(request):
    if request.method != "POST": raise Http404
    if not request.user.can_manage_cash(): raise PermissionDenied("Seul ADMIN peut créer une caisse.")
    form = CashRegisterForm(request.POST)
    if form.is_valid():
        register = form.save()
        messages.success(request, f"Caisse {register.name} créée.")
    else: messages.error(request, "Le nom de caisse est invalide ou déjà utilisé.")
    return redirect("pos:cash-home")


@login_required
def record_cash_movement(request, pk):
    if request.method != "POST": raise Http404
    session = _accessible_session(request, pk)
    form = CashMovementForm(request.POST)
    if form.is_valid():
        try:
            CashSessionService.record_movement(session=session, actor=request.user, **form.cleaned_data)
            messages.success(request, "Mouvement de caisse enregistré.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        errors = "; ".join(f"{field}: {', '.join(error_messages)}" for field, error_messages in form.errors.items())
        messages.error(request, f"Veuillez corriger le mouvement de caisse. {errors}")
    return redirect("pos:cash-home")


@login_required
def record_cash_exchange(request, pk):
    if request.method != "POST": raise Http404
    session = _accessible_session(request, pk)
    form = CashExchangeForm(request.POST)
    if form.is_valid():
        try:
            CashSessionService.record_currency_exchange(session=session, actor=request.user, **form.cleaned_data)
            messages.success(request, "Opération de change enregistrée.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else: messages.error(request, "Veuillez corriger l'opération de change.")
    return redirect("pos:cash-home")


@login_required
def close_cash_session(request, pk):
    session = _accessible_session(request, pk)
    if request.method == "GET":
        transactions = session.cash_transactions.select_related("created_by").exclude(
            category__in=[CashTransaction.Category.EXPENSE, CashTransaction.Category.OPENING_FLOAT]
        )
        return render(request, "pos/cash_close.html", {
            "session": session,
            "report": cash_report_for(session),
            "sales": session.invoices.filter(status="VALIDATED", created_at__date=timezone.localdate()).select_related("cashier").order_by("-created_at"),
            "expenses": session.expenses.filter(status="APPROVED", expense_date=timezone.localdate()).select_related("requester", "approved_by").order_by("-created_at"),
            "cash_transactions": transactions,
            "cash_entries": transactions.filter(direction=CashTransaction.Direction.IN),
            "cash_exits": transactions.filter(direction=CashTransaction.Direction.OUT),
            "close_form": CashSessionCloseForm(),
        })
    if request.method != "POST": raise Http404
    form = CashSessionCloseForm(request.POST)
    if form.is_valid():
        try:
            if cash_report_for(session).total_sales > 0 and not request.POST.get("sales_deposit_local_amount") and not request.POST.get("sales_deposit_foreign_amount"):
                raise ValidationError("Saisissez le versement des ventes en FC et/ou en USD.")
            CashSessionService.close_session(session=session, actor=request.user, sales_deposit_local_amount=form.cleaned_data["sales_deposit_local_amount"], sales_deposit_foreign_amount=form.cleaned_data["sales_deposit_foreign_amount"], counted_local_amount=form.cleaned_data["counted_local_amount"], counted_foreign_amount=form.cleaned_data["counted_foreign_amount"])
            messages.info(request, "Session de vente clôturée.")
            logout(request)
            return redirect("accounts:login")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else: messages.error(request, "Veuillez saisir un montant compté valide.")
    return redirect("pos:cash-close", pk=session.pk)


@login_required
def cash_report(request, pk):
    _accessible_session(request, pk)
    return redirect(f"{reverse('pos:cash-home')}?session={pk}")


@login_required
def void_cash_movement(request, pk, movement_pk):
    if request.method != "POST": raise Http404
    session = _accessible_session(request, pk)
    movement = get_object_or_404(CashTransaction, pk=movement_pk, session=session)
    form = VoidCashMovementForm(request.POST)
    if form.is_valid():
        try:
            CashSessionService.void_movement(movement=movement, actor=request.user, reason=form.cleaned_data["reason"])
            messages.success(request, "Mouvement annulé sans effacer son historique.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("pos:cash-home")


@login_required
def download_session_pdf(request, pk):
    """Génère et sert le PDF de clôture de session (toujours régénéré pour garantir le contenu frais)."""
    session = get_object_or_404(
        CashSession.objects.select_related("register", "cashier"), pk=pk
    )
    if session.cashier_id != request.user.pk and not request.user.can_manage_cash():
        raise PermissionDenied("Vous ne pouvez pas accéder à ce rapport.")
    if session.status != CashSession.Status.CLOSED:
        raise Http404("Le rapport PDF n'est disponible qu'après la clôture de la session.")

    try:
        from apps.reports.pdf import generate_session_pdf
        from apps.expenses.models import Expense
        from apps.core.models import StoreSettings
        from django.core.files.base import ContentFile
        import unicodedata, re as _re

        report   = cash_report_for(session)
        expenses = Expense.objects.filter(
            cash_session=session, status=Expense.Status.APPROVED
        ).order_by("created_at")
        rate = StoreSettings.get_solo().exchange_rate

        pdf_bytes = generate_session_pdf(
            session=session, report=report, expenses=expenses, rate=rate
        )

        # ── Nom de fichier professionnel ────────────────────────────────────
        # Format : Rapport_Cloture_JJMMAAAA_CaisseX_Caissier.pdf
        def _safe(text):
            """Retire accents et caractères non-ASCII pour un nom de fichier sûr."""
            nfkd = unicodedata.normalize('NFKD', str(text))
            ascii_str = nfkd.encode('ascii', 'ignore').decode('ascii')
            return _re.sub(r'[^\w]', '_', ascii_str).strip('_')

        closed_dt = timezone.localtime(session.closed_at)
        date_str   = closed_dt.strftime('%d-%m-%Y')
        register   = _safe(session.register.name)
        cashier    = _safe(session.cashier.get_full_name() or session.cashier.username)
        filename   = f"Rapport_Cloture_{date_str}_{register}_{cashier}.pdf"

        # Sauvegarde (écrase l'ancienne version si elle existe).
        session.report_pdf.save(filename, ContentFile(pdf_bytes), save=True)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        import traceback
        import logging
        logging.getLogger(__name__).exception("Erreur génération PDF session %s", pk)
        messages.error(request, f"Impossible de générer le rapport PDF : {exc}")
        return redirect("pos:cash-sessions")


@login_required
def prev_balance_fragment(request):
    """Vue HTMX : renvoie le solde général de la DERNIÈRE session clôturée
    (toutes caisses confondues). Ce solde peut être réutilisé comme cash initial."""
    if not request.user.can_manage_cash():
        return HttpResponse("")

    last_session = (
        CashSession.objects
        .filter(status=CashSession.Status.CLOSED)
        .select_related("cashier", "register")
        .order_by("-closed_at")
        .first()
    )

    if not last_session:
        return render(request, "pos/_prev_balance.html", {"balance": None})

    from decimal import Decimal, ROUND_HALF_UP
    report = cash_report_for(last_session)

    # Solde général = solde vente + solde cash. Jamais négatif (on clampe à 0).
    ZERO = Decimal("0.00")
    balance_local   = max(ZERO, Decimal(str(report.expected_local  or 0)) + Decimal(str(report.sales_balance or 0)))
    balance_foreign = max(ZERO, Decimal(str(report.expected_foreign or 0)))

    return render(request, "pos/_prev_balance.html", {
        "balance": {
            "local":   balance_local,
            "foreign": balance_foreign,
            "session": last_session,
        }
    })

