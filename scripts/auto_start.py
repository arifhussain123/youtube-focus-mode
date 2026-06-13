#!/usr/bin/env python3
"""Cross-platform one-click startup for the FastAPI backend.

Brings the backend up from a clean checkout with zero manual steps:
  * creates backend/.venv if missing
  * installs requirements.txt on first run (or when it changes)
  * loads backend/.env
  * detects an already-running server (won't start a duplicate)
  * launches uvicorn (dev hot-reload by default; --prod for workers)
  * supervises the process and restarts it if it crashes
  * opens the API docs in a browser once the server is reachable (dev)

Pure standard library so it runs *before* any dependencies are installed.
Works on Windows, Linux, and macOS.

    python scripts/auto_start.py            # dev: hot reload + browser
    python scripts/auto_start.py --prod     # production: workers, no reload
    python scripts/auto_start.py --help     # all flags
"""

import argparse
import hashlib
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

# --- Paths -----------------------------------------------------------------
# Resolve everything relative to this file so cwd doesn't matter.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
VENV_DIR = os.path.join(BACKEND_DIR, ".venv")
REQUIREMENTS = os.path.join(BACKEND_DIR, "requirements.txt")
ENV_FILE = os.path.join(BACKEND_DIR, ".env")
DEPS_MARKER = os.path.join(VENV_DIR, ".deps-installed")  # stores requirements hash

# uvicorn import target — backend/app/main.py exposes `app`, run from backend/.
APP_TARGET = "app.main:app"

IS_WINDOWS = os.name == "nt"


# --- Logging ---------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty() and not IS_WINDOWS
_COLORS = {"INFO": "\033[36m", "WARN": "\033[33m", "ERROR": "\033[31m", "OK": "\033[32m"}
_RESET = "\033[0m"


def log(level, msg):
    stamp = time.strftime("%H:%M:%S")
    tag = f"{_COLORS.get(level, '')}{level}{_RESET}" if _USE_COLOR else level
    print(f"[auto_start {stamp}] {tag} {msg}", flush=True)


# --- venv helpers ----------------------------------------------------------
def venv_python():
    """Path to the venv's Python interpreter for the current OS."""
    if IS_WINDOWS:
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def ensure_venv():
    """Create backend/.venv if its interpreter is missing."""
    if os.path.exists(venv_python()):
        return
    log("INFO", f"Creating virtual environment in {os.path.relpath(VENV_DIR, PROJECT_DIR)} ...")
    try:
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        log("ERROR", f"Failed to create virtual environment: {exc}")
        log("ERROR", "Is Python 3 installed and on your PATH? https://www.python.org/downloads/")
        sys.exit(1)


def _requirements_hash():
    try:
        with open(REQUIREMENTS, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return ""


def ensure_dependencies(force=False):
    """Install requirements.txt when first installing or when it has changed."""
    if not os.path.exists(REQUIREMENTS):
        log("WARN", "No backend/requirements.txt found; skipping dependency install.")
        return

    current = _requirements_hash()
    installed = ""
    if os.path.exists(DEPS_MARKER):
        try:
            with open(DEPS_MARKER, "r", encoding="utf-8") as fh:
                installed = fh.read().strip()
        except OSError:
            installed = ""

    if not force and installed == current:
        log("INFO", "Dependencies already up to date.")
        return

    log("INFO", "Installing dependencies (first run or requirements changed) ...")
    try:
        subprocess.run([venv_python(), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([venv_python(), "-m", "pip", "install", "-r", REQUIREMENTS], check=True)
    except subprocess.CalledProcessError as exc:
        log("ERROR", f"Dependency install failed: {exc}")
        sys.exit(1)

    try:
        with open(DEPS_MARKER, "w", encoding="utf-8") as fh:
            fh.write(current)
    except OSError:
        pass  # marker is an optimization; a missing one just re-installs next time
    log("OK", "Dependencies installed.")


# --- .env ------------------------------------------------------------------
def load_env_file():
    """Parse backend/.env into os.environ (simple KEY=VALUE lines).

    uvicorn also gets --env-file so the server process sees these; loading here
    additionally makes them visible to this launcher. Returns True if found.
    """
    if not os.path.exists(ENV_FILE):
        log("INFO", "No backend/.env found. Watch-time stats work without it; "
                    "copy backend/.env.example to backend/.env to enable categorization.")
        return False
    count = 0
    with open(ENV_FILE, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
                count += 1
    log("INFO", f"Loaded {count} variable(s) from backend/.env")
    return True


# --- Server detection & browser -------------------------------------------
def is_port_open(host, port, timeout=0.5):
    # 127.0.0.1 is the right probe target even when binding 0.0.0.0.
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((probe_host, port)) == 0


def open_browser_when_ready(host, port, timeout=30.0):
    """Poll /health in a background thread, then open the Swagger UI."""
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{probe_host}:{port}"

    def _wait_and_open():
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        log("OK", f"Server is up. Opening {url}/docs")
                        webbrowser.open(f"{url}/docs")
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        log("WARN", "Server did not become reachable in time; skipping browser open.")

    threading.Thread(target=_wait_and_open, daemon=True).start()


# --- uvicorn command -------------------------------------------------------
def build_command(args):
    cmd = [venv_python(), "-m", "uvicorn", APP_TARGET,
           "--host", args.host, "--port", str(args.port)]
    if args.prod:
        cmd += ["--workers", str(args.workers)]
    else:
        cmd += ["--reload"]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    return cmd


# --- Supervisor ------------------------------------------------------------
def run_supervised(args):
    """Run uvicorn, restarting on crash unless told otherwise.

    A crash-loop guard stops after several rapid failures so a broken server
    doesn't spin forever. Ctrl-C shuts down cleanly without restarting.
    """
    cmd = build_command(args)
    mode = "production" if args.prod else "development (hot reload)"
    log("INFO", f"Starting backend in {mode} mode on http://{args.host}:{args.port}")
    log("INFO", "Command: " + " ".join(cmd))

    rapid_failures = 0
    stopping = {"flag": False}

    while True:
        start = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=BACKEND_DIR)

        def _forward(_signum, _frame):
            stopping["flag"] = True
            log("INFO", "Shutting down (signal received) ...")
            try:
                proc.terminate()
            except Exception:
                pass

        previous = signal.signal(signal.SIGINT, _forward)
        try:
            returncode = proc.wait()
        except KeyboardInterrupt:
            stopping["flag"] = True
            proc.terminate()
            returncode = proc.wait()
        finally:
            signal.signal(signal.SIGINT, previous)

        if stopping["flag"]:
            log("INFO", "Backend stopped.")
            return 0

        elapsed = time.monotonic() - start
        if returncode == 0:
            log("INFO", "Backend exited normally.")
            return 0

        if args.no_restart:
            log("ERROR", f"Backend exited with code {returncode}. Restart disabled; quitting.")
            return returncode

        # Crash-loop guard: count failures that happen within 5s of starting.
        if elapsed < 5:
            rapid_failures += 1
        else:
            rapid_failures = 0
        if rapid_failures >= 3:
            log("ERROR", "Backend crashed repeatedly on startup. Giving up — check the logs above.")
            return returncode

        backoff = min(2 ** rapid_failures, 10)
        log("WARN", f"Backend exited with code {returncode}; restarting in {backoff}s ...")
        time.sleep(backoff)


# --- CLI -------------------------------------------------------------------
def parse_args(argv):
    p = argparse.ArgumentParser(description="Auto-start the FastAPI backend.")
    p.add_argument("--prod", action="store_true",
                   help="Production mode: uvicorn workers, no reload, no browser.")
    p.add_argument("--host", default=None, help="Bind host (default 127.0.0.1 dev / 0.0.0.0 prod).")
    p.add_argument("--port", type=int, default=8000, help="Bind port (default 8000).")
    p.add_argument("--workers", type=int, default=2, help="Worker count in --prod (default 2).")
    p.add_argument("--no-browser", action="store_true", help="Do not open the browser.")
    p.add_argument("--no-restart", action="store_true", help="Do not restart on crash.")
    p.add_argument("--reinstall", action="store_true", help="Force reinstall of dependencies.")
    args = p.parse_args(argv)
    if args.host is None:
        args.host = "0.0.0.0" if args.prod else "127.0.0.1"
    return args


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # Already running? Don't start a duplicate.
    if is_port_open(args.host, args.port):
        log("OK", f"Backend already running on http://{args.host}:{args.port} — not starting another.")
        if not args.prod and not args.no_browser:
            probe = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
            webbrowser.open(f"http://{probe}:{args.port}/docs")
        return 0

    ensure_venv()
    ensure_dependencies(force=args.reinstall)
    load_env_file()

    if not args.prod and not args.no_browser:
        open_browser_when_ready(args.host, args.port)

    return run_supervised(args)


if __name__ == "__main__":
    sys.exit(main())
