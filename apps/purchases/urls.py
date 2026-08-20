from django.urls import path
from . import views
app_name="purchases"
urlpatterns=[path("",views.order_list,name="list"),path("<int:pk>/",views.order_detail,name="detail"),path("<int:pk>/lines/",views.add_line,name="line-add"),path("<int:pk>/receive/",views.receive_line,name="receive")]
