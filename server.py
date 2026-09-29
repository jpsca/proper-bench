"""Server entrypoint for the Proper app: `granian --interface wsgi server:app`."""
from app import make_app


app = make_app()
# What `proper run` does before serving: routes, dispatch and views decided
# once, instead of on the first request that needs each of them.
app.lower()
