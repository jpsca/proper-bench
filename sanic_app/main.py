"""The Sanic reference app: the same three routes over the same SQLite file.

Sanic is async through and through, so the database goes through SQLAlchemy's
asyncio extension over aiosqlite, the documented pairing.

    sanic sanic_app.main:app --host 127.0.0.1 --port 8123 --workers 4
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sanic import Sanic, json, text
from sanic.response import html
from sqlalchemy import Column, Integer, Text, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

HERE = Path(__file__).parent
DB_PATH = HERE.parent / "app" / "fortunes.db"

app = Sanic("bench")
Base = declarative_base()
templates = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())
fortunes_template = templates.get_template("fortunes.html")


class Fortune(Base):
    __tablename__ = "fortune"
    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=False)


@app.before_server_start
async def open_db(app, loop):
    # One engine per worker process, created on its own loop.
    app.ctx.engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", pool_size=32)


@app.get("/plaintext")
async def plaintext(request):
    return text("Hello, World!")


@app.get("/json")
async def json_route(request):
    return json({"message": "Hello, World!"})


@app.get("/fortunes")
async def fortunes(request):
    async with request.app.ctx.engine.connect() as conn:
        result = await conn.execute(select(Fortune.id, Fortune.message))
        rows = [{"id": id, "message": message} for id, message in result]
    rows.append({"id": 0, "message": "Additional fortune added at request time."})
    rows.sort(key=lambda r: r["message"])
    return html(fortunes_template.render(fortunes=rows))
