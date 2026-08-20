from django.contrib import admin

from .models import StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Commerce", {"fields": ("name", "address", "contact", "ccm_number", "national_id", "currency", "invoice_prefix", "low_stock_threshold", "expiry_alert_days")} ),
        ("Réductions", {"fields": ("discounts_enabled", "promotion_enabled", "promotion_threshold", "promotion_type", "promotion_value", "manual_discount_limit")} ),
        ("Change", {"fields": ("exchange_rate",)}),
        ("Suivi", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()
