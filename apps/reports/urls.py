from django.urls import path
from .views import report_detail, report_home
app_name="reports"
urlpatterns=[path("",report_home,name="home"), path("<str:day>/", report_detail, name="detail")]
