from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from .forms import CustomerForm
from .models import Customer


@login_required
def customer_list(request):
    if not request.user.can_manage_catalogue():
        raise PermissionDenied
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("customers:list")
    customers = Customer.objects.annotate(order_count=Count("invoices"), spent=Sum("invoices__total")).order_by("name")
    return render(request, "customers/list.html", {"customers": Paginator(customers, 20).get_page(request.GET.get("page")), "form": form})
