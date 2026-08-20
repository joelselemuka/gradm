from django.urls import path
from . import views

app_name = "products"
urlpatterns = [
    path("", views.product_list, name="list"),
    path("new/", views.product_create, name="create"),
    path("labels/print/", views.price_labels_print, name="price-labels-print"),
    path("<int:pk>/edit/", views.product_update, name="update"),
    path("<int:pk>/toggle/", views.product_toggle_active, name="toggle"),
    path("<int:pk>/delete/", views.product_delete, name="delete"),
    path("categories/", views.category_list, name="category-list"),
    path("categories/quick-create/", views.category_quick_create, name="category-quick-create"),
    path("categories/<int:pk>/update/", views.category_update, name="category-update"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category-delete"),
    path("<int:product_pk>/variants/<int:variant_pk>/barcodes/add/", views.barcode_add, name="barcode-add"),
    path("<int:product_pk>/variants/<int:variant_pk>/barcodes/generate/", views.barcode_generate, name="barcode-generate"),
    path("<int:product_pk>/variants/<int:variant_pk>/barcodes/<int:barcode_pk>/deactivate/", views.barcode_deactivate, name="barcode-deactivate"),
    path("<int:product_pk>/variants/<int:variant_pk>/barcodes/print/", views.barcode_print, name="barcode-print"),
    path("<int:pk>/", views.product_detail, name="detail"),
]
