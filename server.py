"""Server entrypoint for the Proper app: `granian --interface wsgi server:app`."""
from app import make_app


app = make_app()
