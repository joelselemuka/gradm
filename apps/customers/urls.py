from django.urls import path
from .views import customer_list
app_name="customers"
urlpatterns=[path("",customer_list,name="list")]
