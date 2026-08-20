from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect,render
from django.utils import timezone
from .models import Notification
@login_required
def notification_list(request): return render(request,"notifications/list.html",{"notifications":Paginator(request.user.notifications.all(), 20).get_page(request.GET.get("page"))})
@login_required
def mark_read(request,pk):
    notice=request.user.notifications.filter(pk=pk).first()
    if notice and not notice.read_at: notice.read_at=timezone.now(); notice.save(update_fields=["read_at"])
    if notice and notice.target_url:
        return redirect(notice.target_url)
    return redirect("notifications:list")
