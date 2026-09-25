"""The FastAPI reference app: the same three routes over the same SQLite file.

SQLAlchemy is used the common way, with sync sessions in `def` endpoints, which
FastAPI runs in its thread pool.
"""
from pathlib import Path

from fastapi import FastAPI, Request
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
