from .views import *
from django.urls import path
app_name = 'article'
urlpatterns = [
    path('list/',product_view,name="product_list_view"),
    path('create/', ProductCreate.as_view(), name='create_product'),
    path('update/<int:pk>/', ProductUpdate.as_view(), name='update_product'),
    path('delete-variant/<int:pk>/', delete_variant, name='delete_variant'),
    path('add-variant/', add_unity, name='add_unity'),
    path('add-category/', add_category, name='add_category'),

    
]
