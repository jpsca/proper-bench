"""The Flask reference app: the same three routes over the same SQLite file,
with Flask-SQLAlchemy, the common pairing."""
from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select

HERE = Path(__file__).parent
DB_PATH = HERE.parent / "app" / "fortunes.db"

app = Flask(__name__, template_folder=str(HERE / "templates"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"check_same_thread": False}, "pool_size": 32,
}
db = SQLAlchemy(app)


class Fortune(db.Model):
    __tablename__ = "fortune"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)


@app.get("/plaintext")
def plaintext():
    return "Hello, World!", {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/json")
def json():
    return jsonify(message="Hello, World!")


@app.get("/fortunes")
def fortunes():
    rows = [
        {"id": id, "message": message}
        for id, message in db.session.execute(select(Fortune.id, Fortune.message))
    ]
    rows.append({"id": 0, "message": "Additional fortune added at request time."})
    rows.sort(key=lambda r: r["message"])
    return render_template("fortunes.html", fortunes=rows)
