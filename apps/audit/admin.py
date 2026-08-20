from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    readonly_fields = ("actor", "action", "target_type", "target_id", "before", "after", "created_at")
    list_display = ("created_at", "action", "actor", "target_type", "target_id")
    def has_delete_permission(self, request, obj=None): return False
