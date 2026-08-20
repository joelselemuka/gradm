from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.dateparse import parse_date
from .models import AuditLog
@login_required
def audit_list(request):
    if not request.user.can_manage_cash(): raise PermissionDenied
    entries = AuditLog.objects.select_related("actor").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    selected_date = request.GET.get("date", "")
    if query:
        entries = entries.filter(Q(action__icontains=query) | Q(actor__username__icontains=query) | Q(target_type__icontains=query))
    if parse_date(selected_date):
        entries = entries.filter(created_at__date=selected_date)
    return render(request,"audit/list.html",{"entries":Paginator(entries, 20).get_page(request.GET.get("page")), "query": query, "selected_date": selected_date})
