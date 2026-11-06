"""Start both applications against disposable storage and check HTTP readiness.

Run with the same Python interpreter used to install both requirements files.
No existing database, uploaded media, or NiceGUI sessions are used or modified.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_url(process, url: str, log_path: Path, timeout: int = 45) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before becoming ready. See {log_path.name}.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return response.read()
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Server did not answer {url} within {timeout}s. See {log_path.name}.")


def stop_server(process) -> None:
    """Stop only this test server, including Windows launcher child processes."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        # A Windows virtualenv launcher's child can retain log handles briefly
        # after the launcher exits. Stop the owned tree before waiting on it.
        stopped = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, text=True, timeout=15,
        )
        if stopped.returncode and process.poll() is None:
            raise RuntimeError(f"Could not stop test server PID {process.pid}: {stopped.stdout.strip()} {stopped.stderr.strip()}")
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def cleanup_workspace(workspace, attempts: int = 20, delay: float = 0.25) -> None:
    """Allow briefly delayed Windows handle release without hiding cleanup errors."""
    for attempt in range(attempts):
        try:
            workspace.cleanup()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def main() -> int:
    processes = []
    workspace = tempfile.TemporaryDirectory(prefix="coverworth-release-smoke-")
    work = Path(workspace.name)
    succeeded = False
    try:
        backend_port, frontend_port = free_port(), free_port()
        while frontend_port == backend_port:
            frontend_port = free_port()
        (work / "release_smoke_settings.py").write_text(
            "from coverworth_backend.settings import *\n"
            f"DATABASES = {{'default': {{'ENGINE': 'django.db.backends.sqlite3', 'NAME': {str(work / 'db.sqlite3')!r}}}}}\n"
            f"MEDIA_ROOT = {str(work / 'media')!r}\n"
            "ALLOWED_HOSTS = ['localhost', '127.0.0.1']\n",
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "release_smoke_settings",
            "PYTHONPATH": os.pathsep.join([str(work), str(ROOT / "backend")]),
            "PYTHONIOENCODING": "utf-8",
            "DEBUG": "True",
            "SECRET_KEY": secrets.token_urlsafe(48),
            "BACKEND_URL": f"http://127.0.0.1:{backend_port}",
            "NICEGUI_HOST": "127.0.0.1",
            "NICEGUI_PORT": str(frontend_port),
            "NICEGUI_STORAGE_PATH": str(work / "nicegui"),
            "NICEGUI_STORAGE_SECRET": secrets.token_urlsafe(48),
        }
        backend_log = work / "backend.log"
        frontend_log = work / "frontend.log"
        with backend_log.open("w", encoding="utf-8") as backend_output, frontend_log.open("w", encoding="utf-8") as frontend_output:
            try:
                subprocess.run(
                    [sys.executable, "manage.py", "migrate", "--noinput"],
                    cwd=ROOT / "backend", env=env,
                    stdout=backend_output, stderr=subprocess.STDOUT, check=True,
                )
                backend = subprocess.Popen(
                    [sys.executable, "manage.py", "runserver", f"127.0.0.1:{backend_port}", "--noreload"],
                    cwd=ROOT / "backend", env=env,
                    stdout=backend_output, stderr=subprocess.STDOUT,
                )
                processes.append(backend)
                health = json.loads(wait_for_url(backend, f"{env['BACKEND_URL']}/api/health/", backend_log))
                if health.get("status") != "ok":
                    raise RuntimeError("Backend health response was not healthy.")
                frontend = subprocess.Popen(
                    [sys.executable, "main.py"], cwd=ROOT / "frontend", env=env,
                    stdout=frontend_output, stderr=subprocess.STDOUT,
                )
                processes.append(frontend)
                page = wait_for_url(frontend, f"http://127.0.0.1:{frontend_port}/", frontend_log)
                if b"CoverWorth" not in page:
                    raise RuntimeError("Frontend did not return the CoverWorth page.")
                succeeded = True
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                print(f"FAIL: {exc}", file=sys.stderr)
                # These are disposable startup processes without logins or live API calls.
                for name, path in [("Backend", backend_log), ("Frontend", frontend_log)]:
                    print(f"\n{name} startup log:\n{path.read_text(encoding='utf-8', errors='replace')}", file=sys.stderr)
            finally:
                for process in reversed(processes):
                    try:
                        stop_server(process)
                    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                        succeeded = False
                        print(f"FAIL: server shutdown: {exc}", file=sys.stderr)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        succeeded = False
        print(f"FAIL: startup preparation: {exc}", file=sys.stderr)
    finally:
        # Both log-file context managers have closed before directory removal.
        try:
            cleanup_workspace(workspace)
        except OSError as exc:
            succeeded = False
            print(f"FAIL: temporary workspace cleanup: {exc}\nTemporary files remain at {work}", file=sys.stderr)

    if succeeded:
        print("PASS: fresh database migrated; backend health and frontend HTTP startup succeeded; test servers stopped and temporary files removed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())