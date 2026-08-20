from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from .forms import SupplierForm
from .models import Supplier


@login_required
def supplier_list(request):
    if not request.user.can_manage_catalogue():
        raise PermissionDenied
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("suppliers:list")
    return render(request, "suppliers/list.html", {"suppliers": Paginator(Supplier.objects.order_by("name"), 20).get_page(request.GET.get("page")), "form": form})
