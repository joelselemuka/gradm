from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
app_name = "accounts"
urlpatterns = [
    path("login/", views.SessionAwareLoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("", views.user_list, name="list"),
    path("new/", views.user_create, name="create"),
    path("<int:pk>/edit/", views.user_update, name="update"),
    path("<int:pk>/toggle/", views.user_toggle_active, name="toggle"),
    path("<int:pk>/delete/", views.user_delete, name="delete"),
]
