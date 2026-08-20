from django.contrib import admin
from .models import CashRegister, CashSession, CashTransaction

admin.site.register([CashRegister, CashSession])


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "session", "direction", "label", "category", "amount", "created_by", "voided_at")
    readonly_fields = ("session", "direction", "label", "category", "amount", "description", "reference", "foreign_currency", "foreign_amount", "exchange_rate", "group_id", "created_by", "created_at", "voided_at", "voided_by", "void_reason")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
