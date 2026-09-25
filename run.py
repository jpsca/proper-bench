"""Run the benchmarks: Proper against Beego, Topcoat, Rails and Django.

    uv run python run.py [--duration 10s] [--connections 64] [--workers 4]
                         [--blocking-threads 4] [--only proper,beego]
                         [--gil-python /path/to/python3.14]

For each server it starts the app, waits for it, warms it up, runs bombardier
against each endpoint, samples the RSS of the whole process tree, stops the
server and prints a Markdown table. Results are also written as JSON to
`results/`.

Every app serves the same three routes over the same SQLite file, `app/fortunes.db`:

- `app/`         Proper, over WSGI and over RSGI, with Granian
- `fastapi_app/` FastAPI + SQLAlchemy, over ASGI, with Granian
- `flask_app/`   Flask + Flask-SQLAlchemy, over WSGI, with Granian
- `django_app/`  Django, over WSGI, with Granian
- `rails_app/` Ruby on Rails, with Puma
- `beego/`    Go, Beego
- `topcoat/`  Rust, Topcoat

Proper and Django run on this project's Python, which is free-threaded; pass
`--gil-python` to add rows on a Python with the GIL. The compiled apps are
built on demand with `go` and `cargo`, looked up on PATH, then in `~/go/bin`
and `~/.cargo/bin`. Go and Rust use every core by default; `--workers` and
`--blocking-threads` apply to Granian and Puma.
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE
RESULTS = HERE / "results"
PORT = 8123
ENDPOINTS = ("/plaintext", "/json", "/fortunes")
BOMBARDIER = shutil.which("bombardier") or str(Path.home() / "go/bin/bombardier")
BEEGO_DIR = HERE / "beego"
BEEGO_BIN = BEEGO_DIR / "beego-bench"
TOPCOAT_DIR = HERE / "topcoat"
TOPCOAT_BIN = TOPCOAT_DIR / "target/release/proper-bench-topcoat"
RAILS_DIR = HERE / "rails_app"
DJANGO_DIR = HERE / "django_app"
# The mise-built Ruby links against libcrypt.so.2, which this distro does not
# ship; a compatibility link lives here (see the README).
RUBY_LIBS = str(Path.home() / ".local/lib")


def tool(name: str, fallback: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    path = Path.home() / fallback
    return str(path) if path.exists() else None


def build_reference_apps() -> None:
    """Compile the Go and Rust apps; skipped, with a note, when the toolchain
    is missing."""
    go = tool("go", "go/bin/go")
    if go:
        subprocess.run([go, "build", "-o", str(BEEGO_BIN), "."], cwd=BEEGO_DIR, check=True)
    else:
        print("go not found, skipping beego", file=sys.stderr)
    cargo = tool("cargo", ".cargo/bin/cargo")
    if cargo:
        subprocess.run([cargo, "build", "--release", "--quiet"], cwd=TOPCOAT_DIR, check=True)
    else:
        print("cargo not found, skipping topcoat", file=sys.stderr)


@dataclass
class Config:
    name: str
    argv: list[str]
    python: str = sys.executable
    env: dict = field(default_factory=dict)
    cwd: str | None = None
    # Copies of the process to start, all on the same port (SO_REUSEPORT),
    # like Proper's PROCESSES setting.
    copies: int = 1


def configs(workers: int, blocking_threads: int, gil_python: str | None) -> list[Config]:
    def granian(name, target, interface, python=sys.executable, env=None, workers=workers, copies=1):
        argv = [
            python, "-m", "granian", target,
            "--interface", interface,
            "--host", "127.0.0.1", "--port", str(PORT),
            "--workers", str(workers), "--log-level", "warning",
            "--no-access-log",
        ]
        if interface == "wsgi":
            argv += ["--blocking-threads", str(blocking_threads)]
        return Config(name, argv, python=python, env=env or {}, copies=copies)

    out = [
        granian("proper wsgi", "server:app", "wsgi"),
        # The same number of threads, split between two interpreters: what
        # `proper run` does with PROCESSES = 2 and half the WORKERS.
        granian(
            "proper wsgi, 2 processes", "server:app", "wsgi",
            workers=max(1, workers // 2), copies=2,
        ),
        granian("proper rsgi", "server:app", "rsgi"),
    ]
    if gil_python:
        out.append(granian("proper wsgi, gil", "server:app", "wsgi", python=gil_python))
        out.append(granian("proper rsgi, gil", "server:app", "rsgi", python=gil_python))
    out.append(granian("fastapi asgi", "fastapi_app.main:app", "asgi"))
    out.append(granian("flask wsgi", "flask_app.main:app", "wsgi"))
    if (DJANGO_DIR / "wsgi.py").exists():
        out.append(granian(
            "django wsgi", "django_app.wsgi:application", "wsgi",
            env={"DJANGO_SETTINGS_MODULE": "django_app.settings"},
        ))
    if (RAILS_DIR / "config.ru").exists():
        out.append(Config("rails (puma)", [
            "bundle", "exec", "puma", "-e", "production", "-b", f"tcp://127.0.0.1:{PORT}",
            "-w", str(workers), "-t", f"{blocking_threads}:{blocking_threads}", "--preload",
        ], env={
            "LD_LIBRARY_PATH": RUBY_LIBS, "RAILS_ENV": "production",
            "SECRET_KEY_BASE": "bench" * 16, "RAILS_LOG_LEVEL": "warn",
        }, cwd=str(RAILS_DIR)))
    if BEEGO_BIN.exists():
        out.append(Config("beego (go)", [str(BEEGO_BIN)], env={"PORT": str(PORT)}))
    if TOPCOAT_BIN.exists():
        out.append(Config("topcoat (rust)", [str(TOPCOAT_BIN)], env={"PORT": str(PORT)}))
    return out


def wait_port(port: int, proc: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with {proc.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def tree_rss_kb(pid: int) -> int:
    """RSS in kB of `pid` and all its descendants."""
    out = subprocess.run(
        ["ps", "-e", "-o", "pid=,ppid=,rss="], capture_output=True, text=True
    ).stdout
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for line in out.splitlines():
        p, pp, r = line.split()
        children.setdefault(int(pp), []).append(int(p))
        rss[int(p)] = int(r)
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        total += rss.get(p, 0)
        stack.extend(children.get(p, []))
    return total


def bombard(url: str, duration: str, connections: int) -> dict:
    out = subprocess.run(
        [BOMBARDIER, "-c", str(connections), "-d", duration, "-l",
         "--print", "r", "--format", "json", url],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)["result"]
    lat = data["latency"]
    return {
        "rps": data["rps"]["mean"],
        "p50_ms": lat["percentiles"]["50"] / 1000,
        "p99_ms": lat["percentiles"]["99"] / 1000,
        "errors": data["others"] + sum(e["count"] for e in data.get("errors", [])),
        "non2xx": data["req1xx"] + data["req3xx"] + data["req4xx"] + data["req5xx"],
    }


def run_config(cfg: Config, duration: str, connections: int) -> dict:
    env = {**os.environ, "PYTHONPATH": str(ROOT), **cfg.env}
    procs = [
        subprocess.Popen(
            cfg.argv, cwd=cfg.cwd or ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True,
        )
        for _ in range(cfg.copies)
    ]
    result: dict = {"name": cfg.name, "endpoints": {}}
    try:
        for p in procs:
            wait_port(PORT, p)
        time.sleep(1.0)
        base = f"http://127.0.0.1:{PORT}"
        for ep in ENDPOINTS:
            bombard(base + ep, "2s", connections)  # warm-up
            result["endpoints"][ep] = bombard(base + ep, duration, connections)
            print(f"  {cfg.name:28} {ep:11} {result['endpoints'][ep]['rps']:>10.0f} rps", flush=True)
        result["rss_mb"] = sum(tree_rss_kb(p.pid) for p in procs) / 1024
    finally:
        for p in procs:
            os.killpg(p.pid, signal.SIGTERM)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            err = p.stderr.read().decode(errors="replace") if p.stderr else ""
            if "Traceback" in err:
                print(err[-2000:], file=sys.stderr)
    return result


def markdown(results: list[dict], meta: dict) -> str:
    lines = [
        f"Workers: {meta['workers']}, connections: {meta['connections']}, "
        f"duration: {meta['duration']} per endpoint, host: {meta['host']}",
        "",
        "| server | plaintext rps | json rps | fortunes rps | fortunes p50 ms | fortunes p99 ms | RSS MB |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        e = r["endpoints"]
        f = e["/fortunes"]
        lines.append(
            f"| {r['name']} | {e['/plaintext']['rps']:,.0f} | {e['/json']['rps']:,.0f} "
            f"| {f['rps']:,.0f} | {f['p50_ms']:.2f} | {f['p99_ms']:.2f} | {r['rss_mb']:.0f} |"
        )
    bad = [(r["name"], ep, v["non2xx"]) for r in results for ep, v in r["endpoints"].items() if v["non2xx"]]
    if bad:
        lines += ["", "Non-2xx responses:"] + [f"- {n} {ep}: {c}" for n, ep, c in bad]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", default="10s")
    ap.add_argument("--connections", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="", help="comma-separated substrings of config names")
    ap.add_argument("--gil-python", default="", help="a Python with the GIL, for extra rows")
    ap.add_argument("--blocking-threads", type=int, default=4,
                    help="threads per worker for the WSGI servers and Puma")
    args = ap.parse_args()

    build_reference_apps()
    cfgs = configs(args.workers, args.blocking_threads, args.gil_python or None)
    if args.only:
        keys = [k.strip() for k in args.only.split(",")]
        cfgs = [c for c in cfgs if any(k in c.name for k in keys)]

    meta = {
        "workers": args.workers, "connections": args.connections,
        "duration": args.duration, "host": os.uname().nodename,
        "cpus": os.cpu_count(), "when": datetime.now(timezone.utc).isoformat(),
    }
    results = []
    for cfg in cfgs:
        print(f"== {cfg.name}", flush=True)
        results.append(run_config(cfg, args.duration, args.connections))

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    report = markdown(results, meta)
    (RESULTS / f"{stamp}.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
