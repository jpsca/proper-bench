from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

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


def pad(request, id):
    return HttpResponse("pad")


def fortunes_index(request):
    rows = list(Fortune.objects.values("id", "message"))
    return render(request, "fortunes/index.html", {"fortunes": rows, "nav_ids": [1, 2, 3]})


def fortunes_show(request, id):
    fortune = get_object_or_404(Fortune, id=id)
    return render(
        request, "fortunes/show.html", {"fortune": fortune, "nav_ids": [1, 2, 3], "current_id": id}
    )
