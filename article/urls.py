from django.urls import path

from .views import *
app_name = 'article'
urlpatterns = [ 
    path("list/", product_list, name="product_list"),
    path("add/", add_product, name="add_product"),
]
