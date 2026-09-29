"""Profile the framework's own cost per request, in process, without a server.

    uv run python profile.py [/plaintext] [--requests 20000] [--sort tottime|cumtime]

Runs the benchmark app's route through the WSGI entry, on this thread, so
the profile shows the pipeline alone: no Granian, no event loop, no worker
thread. It is the path `proper run` serves HTTP on. Prints the time per request
without the profiler, then the profile.
"""
import argparse
import cProfile
import io
import pstats
import time
from io import BytesIO

from app import make_app
from proper.test_client import make_test_request


HEADERS = [("host", "127.0.0.1:8123"), ("user-agent", "bombardier"), ("accept", "*/*")]


def run(app, path: str, count: int) -> None:
    for _ in range(count):
        request = make_test_request(path, headers=HEADERS, app=app)
        response = app._respond_sync(request, BytesIO(b"").read)
        assert response.status == 200, response.status


def main(path: str, requests: int, sort: str) -> None:
    app = make_app()

    run(app, path, 500)  # warm up
    started = time.perf_counter()
    run(app, path, requests)
    per_request = (time.perf_counter() - started) / requests * 1e6
    print(f"{path}: {per_request:.1f} us/request, single thread, no server\n")

    profiler = cProfile.Profile()
    profiler.enable()
    run(app, path, requests // 4)
    profiler.disable()
    out = io.StringIO()
    stats = pstats.Stats(profiler, stream=out).sort_stats(sort)
    stats.print_stats("proper/src" if sort == "cumtime" else 40, 45)
    print(out.getvalue())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="/plaintext")
    ap.add_argument("--requests", type=int, default=20000)
    ap.add_argument("--sort", choices=("tottime", "cumtime"), default="tottime")
    args = ap.parse_args()
    main(args.path, args.requests, args.sort)
