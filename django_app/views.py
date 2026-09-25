from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from .models import Fortune


def plaintext(request):
    return HttpResponse("Hello, World!", content_type="text/plain; charset=utf-8")


def json(request):
    return JsonResponse({"message": "Hello, World!"})


def fortunes(request):
    rows = list(Fortune.objects.values("id", "message"))
    rows.append({"id": 0, "message": "Additional fortune added at request time."})
    rows.sort(key=lambda r: r["message"])
    return render(request, "fortunes.html", {"fortunes": rows})
