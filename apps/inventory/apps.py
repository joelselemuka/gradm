from django.apps import AppConfig
from django.core.signals import request_started


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"

    def ready(self):
        # Run once when the process receives its first request. This is the
        # startup scan without querying PostgreSQL while Django is still
        # loading the application registry; Celery Beat repeats it daily.
        request_started.connect(self._scan_on_first_request, dispatch_uid="inventory_expiry_startup_scan")

    def _scan_on_first_request(self, **kwargs):
        request_started.disconnect(self._scan_on_first_request, dispatch_uid="inventory_expiry_startup_scan")
        try:
            from .tasks import scan_expiration_alerts
            scan_expiration_alerts()
        except Exception:
            # A transient database startup/migration state must not block the
            # first HTTP request. The periodic task will retry the scan.
            pass
