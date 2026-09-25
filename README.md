# proper-bench

Benchmarks of [Proper](https://github.com/jpsca/proper) against other web
frameworks. Every app serves the same three routes, modeled on the TechEmpower
tests, over the same SQLite file (`app/fortunes.db`, created and seeded on the
first run):

- `/plaintext`: static text, the framework's fixed cost per request.
- `/json`: a small dict serialized.
- `/fortunes`: 12 rows read from SQLite, one added, sorted, rendered with a
  template and HTML-escaped. The one that resembles a real page.

| directory     | framework           | server           |
|---------------|---------------------|------------------|
| `app/`        | Proper (Python)     | Granian, WSGI and RSGI |
| `django_app/` | Django (Python)     | Granian, WSGI    |
| `rails_app/`  | Ruby on Rails       | Puma             |
| `beego/`      | Beego (Go)          | its own          |
| `topcoat/`    | Topcoat (Rust)      | its own          |

## Results

2026-09-25, on an Intel Core i5-14400 (6 performance and 4 efficiency cores,
16 hardware threads), Linux, 64 connections, 8 seconds per route. Python
3.14.4 free-threaded, Ruby 3.4.9, Go 1.27, Rust 1.98. Granian and Puma with
4 workers of 4 threads; Go and Rust on every core.

| server            | plaintext rps | json rps | fortunes rps | fortunes p50 | fortunes p99 | RSS    |
|-------------------|--------------:|---------:|-------------:|-------------:|-------------:|-------:|
| Proper 0.26, Granian WSGI | 115,522 | 108,974 |       34,975 |       1.7 ms |       4.3 ms | 181 MB |
| Django 6.1, Granian WSGI  |  54,903 |  51,678 |       10,320 |       5.6 ms |      31.2 ms | 160 MB |
| Rails 8.1, Puma           |   9,797 |  10,598 |        6,610 |       9.6 ms |      13.9 ms | 469 MB |
| Beego 2.3 (Go)            | 303,471 | 266,377 |       31,555 |       1.1 ms |      10.6 ms |  63 MB |
| Topcoat 0.9 (Rust)        | 422,870 | 423,079 |      197,026 |       0.3 ms |       0.8 ms |  16 MB |

RSS is the whole process tree after the run. Beego's fortunes figure moves
between 31k and 35k from run to run; read it and Proper's as even.

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
  sessions; Proper runs its full pipeline.
- bombardier runs on the same machine and competes for CPU: the fastest
  servers are held back by it more than the slow ones are.
