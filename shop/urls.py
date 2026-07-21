from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/<str:name>", views.api, name="api"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="shop/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
