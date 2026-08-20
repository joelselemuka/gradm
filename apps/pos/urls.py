from django.urls import path
from . import views

app_name = "pos"
urlpatterns = [
    path("", views.cash_home, name="cash-home"),
    path("sessions/", views.cash_sessions, name="cash-sessions"),
    path("open/", views.open_cash_session, name="cash-open"),
    path("registers/new/", views.create_cash_register, name="register-create"),
    path("sessions/<int:pk>/", views.cash_report, name="cash-report"),
    path("sessions/<int:pk>/movement/", views.record_cash_movement, name="cash-movement"),
    path("sessions/<int:pk>/exchange/", views.record_cash_exchange, name="cash-exchange"),
    path("sessions/<int:pk>/close/", views.close_cash_session, name="cash-close"),
    path("sessions/<int:pk>/movement/<int:movement_pk>/void/", views.void_cash_movement, name="cash-void"),
    path("sessions/<int:pk>/report.pdf", views.download_session_pdf, name="cash-pdf"),
    path("prev-balance/", views.prev_balance_fragment, name="prev-balance"),
]
