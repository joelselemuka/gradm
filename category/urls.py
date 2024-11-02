from .views import *
from django.urls import path
app_name = 'category'
urlpatterns = [
    path('',category_view,name="category_list_view"),
    path('edit/<int:pk>/',category_update_view,name="category_update_view"),

    path('delete/<int:pk>/',category_delete_view,name="category_delete_view"),
    path('add/',category_add_view,name="category_add_view"),

    
]
