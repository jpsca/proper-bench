"""The route that looks like a page of a real app: `GET /fortunes/:id`.

The concerns a new Proper app's `AppController` carries (origin check,
rate limiting, pagination, form validation, security headers), one row
loaded by id or 404, and a view rendered inside a layout with a nav
partial full of `url_for`. Fifty other resources are registered before
it, so matching it costs what it costs in an app of that size.
"""
from proper import Controller, Route, current, errors
from proper.concerns import FormValidation, OriginProtection, Pagination, RateLimiting

from .models import Fortune
from .security_headers import SecurityHeaders


router = current.app.router


class PadController(Controller):
    """Stands in for the other resources of the app."""

    def show(self):
        return "pad"


for n in range(50):
    router.add_route(Route("GET", f"pad{n}/:id<int>", to=PadController.show, name=f"Pad{n}.show"))


class FortunesController(
    OriginProtection,
    Pagination,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
    Controller,
):
    before = {"do": "set_fortune", "only": "show"}

    @router.get("fortunes/all")
    def index(self):
        self.fortunes = list(Fortune.select().dicts())

    @router.get("fortunes/:id<int>")
    def show(self):
        pass

    # Private

    def set_fortune(self):
        self.fortune = Fortune.find(self.params["id"])
        if self.fortune is None:
            raise errors.NotFound
