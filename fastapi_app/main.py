"""The FastAPI reference app: the same three routes over the same SQLite file.

SQLAlchemy is used the common way, with sync sessions in `def` endpoints, which
FastAPI runs in its thread pool.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base

HERE = Path(__file__).parent
DB_PATH = HERE.parent / "app" / "fortunes.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}, pool_size=32
)
Base = declarative_base()


class Fortune(Base):
    __tablename__ = "fortune"
    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=False)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=str(HERE / "templates"))


@app.get("/plaintext", response_class=PlainTextResponse)
def plaintext():
    return "Hello, World!"


@app.get("/json")
def json():
    return {"message": "Hello, World!"}


@app.get("/fortunes")
def fortunes(request: Request):
    with Session(engine) as session:
        rows = [
            {"id": id, "message": message}
            for id, message in session.execute(select(Fortune.id, Fortune.message))
        ]
    rows.append({"id": 0, "message": "Additional fortune added at request time."})
    rows.sort(key=lambda r: r["message"])
    return templates.TemplateResponse(request, "fortunes.html", {"fortunes": rows})


# --- The page route: what a CRUD app's "show" does ---

SECURITY_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "X-Download-Options": "noopen",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class OriginAndSecurityHeaders:
    """A plain ASGI middleware: an origin check for state-changing requests
    (reads go through) and the security headers on every response. Not
    `@app.middleware("http")`, whose `BaseHTTPMiddleware` halves throughput."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            headers = {k: v for k, v in scope["headers"]}
            origin = headers.get(b"origin")
            sec_fetch_site = headers.get(b"sec-fetch-site")
            same = (origin is None and sec_fetch_site is None) or sec_fetch_site in (b"same-origin", b"none")
            if not same and not (origin and origin.split(b"//", 1)[-1] == headers.get(b"host")):
                return await PlainTextResponse("Forbidden", status_code=403)(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                present = {k for k, _ in message["headers"]}
                message["headers"] = list(message["headers"]) + [
                    (k, v) for k, v in SECURITY_HEADERS_RAW if k not in present
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)


SECURITY_HEADERS_RAW = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
app.add_middleware(OriginAndSecurityHeaders)


def pad(id: int):
    return PlainTextResponse("pad")


# Fifty other resources, registered before the page, as in an app of that size.
for n in range(50):
    app.add_api_route(f"/pad{n}/{{id}}", pad, name=f"pad{n}")


@app.get("/fortunes/all", name="fortunes_index")
def fortunes_index(request: Request):
    with Session(engine) as session:
        rows = session.execute(select(Fortune.id, Fortune.message)).all()
    return templates.TemplateResponse(request, "fortunes/index.html", {"fortunes": rows})


@app.get("/fortunes/{id}", name="fortunes_show")
def fortunes_show(request: Request, id: int):
    with Session(engine) as session:
        fortune = session.get(Fortune, id)
        if fortune is None:
            raise HTTPException(status_code=404)
        context = {"fortune": {"id": fortune.id, "message": fortune.message}, "current_id": id}
    return templates.TemplateResponse(request, "fortunes/show.html", context)
