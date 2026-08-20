from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from apps.audit.services import audit
from apps.pos.models import CashSession
from .forms import UserCreateForm, UserUpdateForm
from .models import User


class SessionAwareLoginView(auth_views.LoginView):
    """Vue de connexion avec protection anti-force-brute et validation de session caisse."""

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        if user.can_operate_pos() and not CashSession.objects.filter(
            cashier_id=user.pk,
            status=CashSession.Status.OPEN,
        ).exists():
            form.add_error(None, "Aucune session ouverte pour cet utilisateur")
            return self.form_invalid(form)
        return super().form_valid(form)


def _admin(request):
    if not request.user.can_manage_cash(): raise PermissionDenied("Gestion des utilisateurs réservée à ADMIN.")


@login_required
def user_list(request):
    _admin(request)
    return render(request, "accounts/list.html", {"users": Paginator(User.objects.order_by("username"), 20).get_page(request.GET.get("page"))})


@login_required
def user_create(request):
    _admin(request); form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(actor=request.user, action="USER_CREATED", target=user, after={"username": user.username, "role": user.role})
        messages.success(request, f"Compte {user.username} créé.")
        return redirect("accounts:list")
    return render(request, "accounts/form.html", {"form": form, "title": "Créer un utilisateur"})


@login_required
def user_update(request, pk):
    _admin(request); target = get_object_or_404(User, pk=pk); form = UserUpdateForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        before = {"role": target.role, "is_active": target.is_active}
        form.save()
        target.refresh_from_db()
        audit(actor=request.user, action="USER_UPDATED", target=target, before=before, after={"role": target.role, "is_active": target.is_active})
        messages.success(request, "Utilisateur mis à jour.")
        return redirect("accounts:list")
    return render(request, "accounts/form.html", {"form": form, "title": f"Modifier {target.username}"})


@login_required
def user_toggle_active(request, pk):
    _admin(request)
    if request.method == "POST":
        target = get_object_or_404(User, pk=pk)
        if target.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        else:
            before = {"is_active": target.is_active}
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            audit(actor=request.user, action="USER_TOGGLED", target=target, before=before, after={"is_active": target.is_active})
            messages.success(request, "Statut du compte mis à jour.")
    return redirect("accounts:list")


@login_required
def user_delete(request, pk):
    _admin(request)
    if request.method == "POST":
        target = get_object_or_404(User, pk=pk)
        if target.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        else:
            try:
                before = {"username": target.username, "role": target.role}
                target.delete()
                audit(actor=request.user, action="USER_DELETED", target=request.user, before=before)
                messages.success(request, "Compte supprimé.")
            except ProtectedError:
                messages.error(request, "Ce compte a un historique métier ; il a été conservé. Désactivez-le plutôt.")
    return redirect("accounts:list")
