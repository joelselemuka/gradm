from .views import *
from django.urls import path
app_name = 'article'
urlpatterns = [
    path('',product_view,name="product_list_view"),
    path('edit/<int:pk>/',Product_update_view,name="product_update_view"),

    path('delete/<int:pk>/',Product_delete_view,name="product_delete_view"),
    path('add/',product_add_view,name="product_add_view"),

    
]
