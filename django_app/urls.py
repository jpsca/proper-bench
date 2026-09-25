from django.urls import path

from . import views

urlpatterns = [
    path("plaintext", views.plaintext),
    path("json", views.json),
    path("fortunes", views.fortunes),
]
