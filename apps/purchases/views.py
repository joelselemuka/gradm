from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from .forms import PurchaseLineForm, PurchaseOrderForm, ReceivePurchaseLineForm
from .models import PurchaseOrder, ReplenishmentNeed
from .services import PurchaseService

def _allowed(request):
    if not request.user.can_manage_inventory(): raise PermissionDenied

@login_required
def order_list(request):
    _allowed(request); form=PurchaseOrderForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        order=form.save(commit=False); order.created_by=request.user; order.save(); messages.success(request,"Commande créée. Ajoutez les lignes."); return redirect("purchases:detail",pk=order.pk)
    return render(request,"purchases/list.html",{"orders":Paginator(PurchaseOrder.objects.select_related("supplier").order_by("-created_at"), 20).get_page(request.GET.get("page")),"needs":ReplenishmentNeed.objects.filter(status=ReplenishmentNeed.Status.OPEN).select_related("variant__product"),"form":form})

@login_required
def order_detail(request,pk):
    _allowed(request); order=get_object_or_404(PurchaseOrder.objects.select_related("supplier","cash_session").prefetch_related("lines__variant__product"),pk=pk)
    return render(request,"purchases/detail.html",{"order":order,"line_form":PurchaseLineForm(),"receive_form":ReceivePurchaseLineForm(order=order)})

@login_required
def add_line(request,pk):
    _allowed(request); order=get_object_or_404(PurchaseOrder,pk=pk); form=PurchaseLineForm(request.POST)
    if form.is_valid() and order.status==PurchaseOrder.Status.DRAFT:
        line=form.save(commit=False); line.order=order
        try: line.save(); messages.success(request,"Ligne ajoutée.")
        except Exception: messages.error(request,"Cet article est déjà dans la commande.")
    return redirect("purchases:detail",pk=pk)

@login_required
def receive_line(request,pk):
    _allowed(request); order=get_object_or_404(PurchaseOrder,pk=pk); form=ReceivePurchaseLineForm(request.POST,order=order)
    if form.is_valid():
        try: PurchaseService.receive_line(order=order,line=form.cleaned_data["line"],actor=request.user,quantity=form.cleaned_data["quantity"],lot_code=form.cleaned_data["lot_code"],expires_at=form.cleaned_data["expires_at"]); messages.success(request,"Réception enregistrée.")
        except (ValidationError,PermissionDenied) as exc: messages.error(request,"; ".join(exc.messages) if hasattr(exc,"messages") else str(exc))
    return redirect("purchases:detail",pk=pk)
