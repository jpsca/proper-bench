"""The Flask reference app: the same three routes over the same SQLite file,
with Flask-SQLAlchemy, the common pairing."""
from pathlib import Path

from flask import Blueprint, Flask, abort, jsonify, render_template, request
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


# --- The page route: what a CRUD app's "show" does ---
#
# The hooks live on a blueprint, so they run for the page routes and not for
# the three TechEmpower ones, like the concerns of Proper's page controller.

pages = Blueprint("pages", __name__)

SECURITY_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "X-Download-Options": "noopen",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@pages.before_request
def check_request_origin():
    """Reject cross-site state-changing requests; reads are let through."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    origin = request.headers.get("Origin")
    sec_fetch_site = request.headers.get("Sec-Fetch-Site")
    if (origin is None and sec_fetch_site is None) or sec_fetch_site in ("same-origin", "none"):
        return None
    if origin and origin.split("//", 1)[-1] == request.host:
        return None
    abort(403)


@pages.after_request
def set_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def pad(id):
    return "pad"


# Fifty other resources, registered before the page, as in an app of that size.
for n in range(50):
    pages.add_url_rule(f"/pad{n}/<int:id>", endpoint=f"pad{n}", view_func=pad)


@pages.get("/fortunes/all")
def fortunes_index():
    rows = db.session.execute(select(Fortune.id, Fortune.message)).all()
    return render_template("fortunes/index.html", fortunes=rows)


@pages.get("/fortunes/<int:id>")
def fortunes_show(id):
    fortune = db.get_or_404(Fortune, id)
    return render_template("fortunes/show.html", fortune=fortune, current_id=id)


app.register_blueprint(pages)
