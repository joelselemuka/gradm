from django.urls import path
from .views import dashboard, dashboard_expenses, store_settings

app_name = "core"
urlpatterns = [path("", dashboard, name="dashboard"), path("dashboard/expenses/", dashboard_expenses, name="dashboard-expenses"), path("settings/", store_settings, name="settings")]
