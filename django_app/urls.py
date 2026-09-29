from django.urls import path

from . import views


# Fifty other resources, registered before the page, as in an app of that size.
urlpatterns = [path(f"pad{n}/<int:id>", views.pad, name=f"pad{n}") for n in range(50)]
urlpatterns += [
    path("plaintext", views.plaintext),
    path("json", views.json),
    path("fortunes", views.fortunes),
    path("fortunes/all", views.fortunes_index, name="fortunes_index"),
    path("fortunes/<int:id>", views.fortunes_show, name="fortunes_show"),
]
