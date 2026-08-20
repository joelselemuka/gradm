from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("apps.accounts.urls")),
    path("products/", include("apps.products.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("sales/", include("apps.sales.urls")),
    path("suppliers/", include("apps.suppliers.urls")),
    path("purchases/", include("apps.purchases.urls")),
    path("customers/", include("apps.customers.urls")),
    path("reports/", include("apps.reports.urls")),
    path("promotions/", include("apps.promotions.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("audit/", include("apps.audit.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("cash/", include("apps.pos.urls")),
    path("", include("apps.core.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
