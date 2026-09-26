# proper-bench

Benchmarks of [Proper](https://github.com/jpsca/proper) against other web
frameworks. Every app serves the same three routes, modeled on the TechEmpower
tests, over the same SQLite file (`app/fortunes.db`, created and seeded on the
first run):

- `/plaintext`: static text, the framework's fixed cost per request.
- `/json`: a small dict serialized.
- `/fortunes`: 12 rows read from SQLite, one added, sorted, rendered with a
  template and HTML-escaped. The one that resembles a real page.

| directory      | framework                    | server                 |
|----------------|------------------------------|------------------------|
| `app/`         | Proper (Python)              | Granian, WSGI and RSGI |
| `flask_app/`   | Flask + Flask-SQLAlchemy     | Granian, WSGI          |
| `django_app/`  | Django                       | Granian, WSGI          |
| `fastapi_app/` | FastAPI + SQLAlchemy         | Granian, ASGI          |
| `litestar_app/`| Litestar + SQLAlchemy        | Granian, ASGI          |
| `sanic_app/`   | Sanic + SQLAlchemy asyncio   | Sanic's own server     |
| `rails_app/`  | Ruby on Rails       | Puma             |
| `beego/`       | Beego (Go)                   | its own                |
| `actix/`       | Actix Web + sqlx + askama (Rust) | its own            |
| `topcoat/`     | Topcoat + Toasty (Rust)      | its own                |

## Results

2026-09-25, on an Intel Core i5-14400 (6 performance and 4 efficiency cores,
16 hardware threads), Linux, 64 connections, 8 seconds per route, all rows
from one run. Python 3.14.4 free-threaded, Ruby 3.4.9, Go 1.27, Rust 1.98.
Granian and Puma with 16 threads in total: 4 workers of 4 threads, or for
Proper's second row 2 processes of 2 workers of 4 threads, which is what
`proper run` does with `PROCESSES = 2`. FastAPI and Litestar run 4 ASGI
workers and their own thread pools for the sync endpoints; Sanic runs 4 of
its own worker processes. Go and Rust use every core.

| server                                   | plaintext rps | json rps | fortunes rps | fortunes p50 | fortunes p99 | RSS    |
|------------------------------------------|--------------:|---------:|-------------:|-------------:|-------------:|-------:|
| Proper 0.26, Granian WSGI                |       116,828 |  108,427 |       35,063 |       1.7 ms |       4.3 ms | 187 MB |
| Proper 0.26, 2 processes                 |       129,495 |  118,494 |       34,151 |       1.7 ms |       4.4 ms | 316 MB |
| Flask 3.1 + SQLAlchemy, Granian WSGI     |        76,252 |   72,359 |       13,669 |       3.0 ms |      40.0 ms | 196 MB |
| Litestar 2.24 + SQLAlchemy, Granian ASGI |       100,935 |   97,398 |       12,239 |       3.6 ms |      50.5 ms | 263 MB |
| FastAPI 0.141 + SQLAlchemy, Granian ASGI |        49,334 |   44,351 |       11,767 |       3.3 ms |      61.3 ms | 313 MB |
| Sanic 25.12 + SQLAlchemy asyncio, own server | 149,176 |  133,980 |       10,300 |       5.6 ms |      10.5 ms | 606 MB |
| Django 6.1, Granian WSGI                 |        56,310 |   51,340 |       10,097 |       5.7 ms |      31.9 ms | 164 MB |
| Rails 8.1, Puma                          |         9,685 |   10,072 |        6,454 |       9.9 ms |      13.0 ms | 491 MB |
| Beego 2.3 (Go)                           |       318,146 |  257,260 |       31,138 |       1.2 ms |      10.7 ms |  63 MB |
| Actix Web 4.15 + sqlx + askama (Rust)    |       630,327 |  620,509 |       48,497 |       1.1 ms |       4.4 ms |  19 MB |
| Topcoat 0.9 + Toasty (Rust)              |       321,294 |  324,361 |      181,794 |       0.3 ms |       1.0 ms |  17 MB |

RSS is the whole process tree after the run. Between runs, Proper's plaintext
moves within about 10%, Beego's fortunes between 31k and 36k, and the two Rust
servers' plaintext by 20% or more (they are the ones bombardier holds back);
read Proper and Beego on fortunes as even. SQLAlchemy 2.1 has no compiled
wheel for free-threaded Python yet, so the SQLAlchemy apps run its pure-Python
paths. Sanic's plaintext comes from uvloop, httptools and four processes with
nothing shared; its fortunes number is where the async database path costs.
Actix's fortunes number is bounded by sqlx, whose SQLite driver runs each
query on a blocking thread; Topcoat's Toasty talks to SQLite directly.

## Running

```sh
uv sync                                   # Python 3.14t, Proper from ../proper, Django
uv run python run.py                      # everything, 10s per route
uv run python run.py --only proper,beego --duration 5s
```

Results are printed as a Markdown table and saved under `results/`.
`--workers` and `--blocking-threads` (default 4 and 4) apply to Granian and to
Puma; Go and Rust use every core. `--gil-python /path/to/python3.14` adds rows
for Proper on a Python with the GIL.

Other tools:

```sh
uv run python profile.py /fortunes        # cProfile of Proper's pipeline, in process
uv run python threads.py /plaintext       # how Proper scales across threads in one process
```

## Requirements

- [uv](https://docs.astral.sh/uv/); it installs Python 3.14t itself.
- [bombardier](https://github.com/codesenberg/bombardier) on PATH or in `~/go/bin`.
- Go, on PATH or in `~/go/bin`, for Beego. Skipped if missing.
- Rust (`cargo`), on PATH or in `~/.cargo/bin`, for Actix and Topcoat. Skipped if missing.
- Ruby 3.4 with Bundler for Rails; run `bundle install` in `rails_app/`.
  Skipped if `rails_app/config.ru` is missing. A Ruby built by mise for
  another distro may need `libcrypt.so.2`: `ln -s /lib/x86_64-linux-gnu/libcrypt.so.1
  ~/.local/lib/libcrypt.so.2`; the harness adds `~/.local/lib` to
  `LD_LIBRARY_PATH` for Puma.

## Fairness notes

- All apps read the same table; each one creates it if missing.
- Compression is off everywhere.
- Rails runs in production mode with `skip_forgery_protection` on these
  routes; Django runs its standard middleware stack, with signed-cookie
  sessions; Flask and FastAPI run as generated, with no extra middleware;
  Proper runs its full pipeline.
- The SQLAlchemy apps use sync sessions, the common way; FastAPI and Litestar
  run those endpoints in their thread pools. Sanic, being async throughout,
  uses SQLAlchemy's asyncio extension over aiosqlite.
- bombardier runs on the same machine and competes for CPU: the fastest
  servers are held back by it more than the slow ones are.
