from .views import *
from django.urls import path

app_name = 'unity'
urlpatterns = [
    path('list/', unity_view, name="unity_list_view"),
    path('edit/<int:pk>/', unity_update_view, name="unity_update_view"),

    path('delete/<int:pk>/', unity_delete_view, name="unity_delete_view"),
    path('add/', unity_add_view, name="unity_add_view"),

]
