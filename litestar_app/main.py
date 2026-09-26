"""The Litestar reference app: the same three routes over the same SQLite file.

SQLAlchemy is used the common way, with sync sessions in sync handlers, which
Litestar runs in its thread pool.
"""
from pathlib import Path

from litestar import Litestar, Request, get
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.response import Template
from litestar.template.config import TemplateConfig
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


@get("/plaintext", media_type="text/plain", sync_to_thread=False)
def plaintext() -> str:
    return "Hello, World!"


@get("/json", sync_to_thread=False)
def json() -> dict:
    return {"message": "Hello, World!"}


@get("/fortunes", sync_to_thread=True)
def fortunes(request: Request) -> Template:
    with Session(engine) as session:
        rows = [
            {"id": id, "message": message}
            for id, message in session.execute(select(Fortune.id, Fortune.message))
        ]
    rows.append({"id": 0, "message": "Additional fortune added at request time."})
    rows.sort(key=lambda r: r["message"])
    return Template(template_name="fortunes.html", context={"fortunes": rows})


app = Litestar(
    route_handlers=[plaintext, json, fortunes],
    template_config=TemplateConfig(directory=HERE / "templates", engine=JinjaTemplateEngine),
    openapi_config=None,
    debug=False,
)
