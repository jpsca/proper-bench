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
| `rails_app/`  | Ruby on Rails       | Puma             |
| `beego/`      | Beego (Go)          | its own          |
| `topcoat/`    | Topcoat (Rust)      | its own          |

## Results

2026-09-25, on an Intel Core i5-14400 (6 performance and 4 efficiency cores,
16 hardware threads), Linux, 64 connections, 8 seconds per route, all rows
from one run. Python 3.14.4 free-threaded, Ruby 3.4.9, Go 1.27, Rust 1.98.
Granian and Puma with 16 threads in total: 4 workers of 4 threads, or for
Proper's second row 2 processes of 2 workers of 4 threads, which is what
`proper run` does with `PROCESSES = 2`. FastAPI runs 4 ASGI workers and its
own thread pool for the sync endpoints. Go and Rust use every core.

| server                              | plaintext rps | json rps | fortunes rps | fortunes p50 | fortunes p99 | RSS    |
|-------------------------------------|--------------:|---------:|-------------:|-------------:|-------------:|-------:|
| Proper 0.26, Granian WSGI           |       115,945 |  109,762 |       35,130 |       1.7 ms |       4.3 ms | 185 MB |
| Proper 0.26, 2 processes            |       130,966 |  121,071 |       34,084 |       1.7 ms |       4.6 ms | 317 MB |
| Flask 3.1 + SQLAlchemy, Granian WSGI |       78,355 |   72,738 |       13,957 |       3.1 ms |      42.1 ms | 192 MB |
| Django 6.1, Granian WSGI            |        55,801 |   51,790 |       10,306 |       4.7 ms |      31.1 ms | 162 MB |
| FastAPI 0.141 + SQLAlchemy, Granian ASGI |   44,983 |   42,384 |       11,509 |       3.5 ms |      60.4 ms | 320 MB |
| Rails 8.1, Puma                     |         9,782 |   10,420 |        6,530 |       9.6 ms |      13.7 ms | 470 MB |
| Beego 2.3 (Go)                      |       317,831 |  282,084 |       35,884 |       1.0 ms |       9.1 ms |  62 MB |
| Topcoat 0.9 (Rust)                  |       423,709 |  418,326 |      200,165 |       0.3 ms |       0.8 ms |  17 MB |

RSS is the whole process tree after the run. Between runs, Proper's plaintext
moves within about 10% and Beego's fortunes between 31k and 36k; read Proper
and Beego on fortunes as even. SQLAlchemy 2.1 has no compiled wheel for
free-threaded Python yet, so Flask and FastAPI run its pure-Python paths.

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
- Rust (`cargo`), on PATH or in `~/.cargo/bin`, for Topcoat. Skipped if missing.
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
- The SQLAlchemy apps use sync sessions, the common way; FastAPI runs those
  endpoints in its thread pool.
- bombardier runs on the same machine and competes for CPU: the fastest
  servers are held back by it more than the slow ones are.
