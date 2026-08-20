from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from apps.pos.models import CashSession
from .forms import DecisionForm, ExpenseForm
from .models import Expense
from .services import ExpenseService

@login_required
def expense_list(request):
    expenses=Expense.objects.select_related("requester","approved_by","cash_session__register").order_by("-created_at")
    is_admin = request.user.can_approve_expense()
    # A cashier's history is scoped to the session that is open right now.
    # Filtering only by requester would expose yesterday's closed-session
    # expenses on the current POS screen.
    active_session = CashSession.objects.select_related("register").filter(
        cashier=request.user,
        status=CashSession.Status.OPEN,
    ).first()
    if not is_admin:
        expenses = expenses.filter(
            requester=request.user,
            cash_session=active_session,
        ) if active_session else expenses.none()
    selected_date = request.GET.get("date", "")
    selected_session = request.GET.get("session", "")
    selected_user = request.GET.get("user", "")
    if parse_date(selected_date): expenses = expenses.filter(expense_date=selected_date)
    if is_admin and selected_user.isdigit(): expenses = expenses.filter(requester_id=selected_user)
    if is_admin and selected_session.isdigit(): expenses = expenses.filter(cash_session_id=selected_session)
    sessions = CashSession.objects.select_related("register", "cashier").order_by("-opened_at")
    if is_admin:
        cashiers = get_user_model().objects.filter(role__in=[get_user_model().Role.CASHIER, get_user_model().Role.MANAGER]).order_by("username")
    else:
        cashiers = [request.user]
    form = ExpenseForm(request.POST or None) if request.user.role == request.user.Role.CASHIER else None
    if request.method == "POST":
        if form is None:
            raise PermissionDenied("Seul un caissier peut créer une dépense.")
        if form.is_valid():
            try:
                ExpenseService.submit(actor=request.user, **form.cleaned_data)
                messages.success(request,"Dépense soumise pour approbation.")
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            return redirect("expenses:list")
    return render(request,"expenses/list.html",{"expenses":Paginator(expenses, 20).get_page(request.GET.get("page")),"form":form,"decision_form":DecisionForm(),"is_admin_view":is_admin,"active_session":active_session,"sessions":sessions[:100],"cashiers":cashiers,"selected_date":selected_date,"selected_session":selected_session,"selected_user":selected_user})

@login_required
def expense_detail(request, pk):
    expense = get_object_or_404(Expense.objects.select_related("requester", "approved_by", "cash_session__register"), pk=pk)
    if not request.user.can_approve_expense() and expense.requester_id != request.user.pk:
        raise PermissionDenied("Cette dépense ne vous est pas accessible.")
    return render(request, "expenses/detail.html", {"expense": expense, "decision_form": DecisionForm(), "is_admin_view": request.user.can_approve_expense()})

@login_required
def expense_decision(request,pk,decision):
    if request.method!="POST": return redirect("expenses:list")
    expense=get_object_or_404(Expense,pk=pk); form=DecisionForm(request.POST)
    if form.is_valid():
        try:
            if decision=="approve": ExpenseService.approve(expense=expense,actor=request.user,comment=form.cleaned_data["comment"])
            else: ExpenseService.reject(expense=expense,actor=request.user,comment=form.cleaned_data["comment"])
            messages.success(request,"Décision enregistrée.")
        except (ValidationError,PermissionDenied) as exc: messages.error(request,"; ".join(exc.messages) if hasattr(exc,"messages") else str(exc))
    return redirect("expenses:detail", pk=pk)
