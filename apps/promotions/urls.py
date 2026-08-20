from django.urls import path
from .views import promotion_list
app_name="promotions"; urlpatterns=[path("",promotion_list,name="list")]
