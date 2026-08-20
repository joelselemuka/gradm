from django.urls import path
from . import views

app_name = "sales"
urlpatterns = [
    path("pos/", views.pos, name="pos"), path("pos/cart/add/", views.cart_add, name="cart-add"), path("pos/cart/<int:variant_id>/", views.cart_update, name="cart-update"), path("pos/preview/", views.checkout_preview, name="checkout-preview"), path("pos/checkout/", views.checkout, name="checkout"),
    path("invoices/", views.invoice_list, name="invoice-list"), path("invoices/<int:pk>/", views.invoice_detail, name="invoice-detail"), path("invoices/<int:pk>/cancel/", views.cancel_invoice, name="invoice-cancel"),
]
