from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from .forms import PromotionForm
from .models import Promotion


@login_required
def promotion_list(request):
    if not request.user.can_manage_catalogue():
        raise PermissionDenied
    form = PromotionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("promotions:list")
    promotions = Promotion.objects.select_related("variant__product", "category").order_by("-priority")
    return render(request, "promotions/list.html", {"promotions": Paginator(promotions, 20).get_page(request.GET.get("page")), "form": form})
