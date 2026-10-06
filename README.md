# proper-bench

Benchmarks of [Proper](https://github.com/jpsca/proper) against other web
frameworks. Every app serves the same three routes, modeled on the TechEmpower
tests, over the same SQLite file (`app/fortunes.db`, created and seeded on the
first run):

- `/plaintext`: static text, the framework's fixed cost per request.
- `/json`: a small dict serialized.
- `/fortunes`: 12 rows read from SQLite, one added, sorted, rendered with a
  template and HTML-escaped. The one that resembles a real page.
- `/fortunes/7`: a page of a real app, the "show" of a CRUD resource: the
  filters a new Proper app runs on every request (origin check, rate
  limiting, pagination and security headers), one row loaded by id or
  404, and a view rendered inside a layout with a nav partial full of URL
  helpers, in an app with fifty other resources registered. Every app serves it except Rails, Sanic, Litestar and
  Topcoat, which show "-" for it.

| framework                                | plaintext rps |    json rps | fortunes rps | fortunes p50 ms | fortunes p99 ms |   page rps | page p99 ms |  RSS MB |
|----------------------------------------- | ------------: | ----------: | -----------: | --------------: | --------------: | ---------: | ----------: | ------: |
| Rails 8.1, Puma                          |        10,400 |      11,087 |        6,774 |             9.3 |            14.9 |          - |           - |     476 |
| Django 6.1, Granian WSGI                 |        56,189 |      53,087 |        9,773 |             5.6 |            30.6 |      9,261 |        34.2 |     145 |
| Sanic 25.12 + SQLAlchemy asyncio         |       160,871 |     146,739 |       10,453 |             5.9 |             8.3 |          - |           - |     618 |
| FastAPI 0.141 + SQLAlchemy, Granian ASGI |        53,167 |      49,233 |       12,382 |             2.9 |            69.3 |      7,146 |        13.5 |     325 |
| Litestar 2.24 + SQLAlchemy, Granian ASGI |       114,245 |     112,688 |       12,476 |             3.3 |            56.3 |          - |           - |     272 |
| Flask 3.1 + SQLAlchemy, Granian WSGI     |        83,136 |      79,016 |       14,925 |             2.7 |            37.9 |     17,422 |         6.9 |     187 |
| Beego 2.3 (Go)                           |       346,835 |     308,574 |       36,525 |             1.1 |             8.6 |     42,257 |         7.7 |      65 |
| Actix Web 4.15 + sqlx + askama (Rust)    |       796,488 |     764,614 |       49,319 |             1.2 |             3.3 |    187,302 |         1.4 |      37 |
| **Proper 0.34, Granian WSGI**            |   **129,313** | **122,407** |   **49,559** |         **1.3** |         **2.6** | **50,488** |     **2.7** | **114** |
| Topcoat 0.9 + Toasty (Rust)              |       437,137 |     445,011 |      207,689 |             0.3 |             0.8 |          - |           - |      17 |

RSS is the whole process tree after the run. Between runs, Proper's plaintext
moves within about 10%, Beego's fortunes between 31k and 36k, and the two Rust
servers' plaintext by 20% or more (they are the ones bombardier holds back).
SQLAlchemy 2.1 has no compiled
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
