from django.urls import path
from .views import supplier_list
app_name = "suppliers"
urlpatterns = [path("", supplier_list, name="list")]
