"""Fixtures for the frontend <-> backend integration tests.

A real Django server is started once per test session against a freshly
migrated, throwaway SQLite database (the development db.sqlite3 is never
touched). The NiceGUI pages are driven with NiceGUI's simulated `user`
fixture and talk to that server over HTTP, exactly like in production.
"""

import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from pathlib import Path

import pytest
import requests


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
BACKEND_PORT = _free_port()

# Must be set before any frontend/NiceGUI module reads them at import time.
os.environ["BACKEND_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
# NiceGUI wipes its storage folder between tests; keep it away from frontend/.nicegui.
os.environ["NICEGUI_STORAGE_PATH"] = tempfile.mkdtemp(prefix="coverworth-nicegui-")

pytest_plugins = ["nicegui.testing.user_plugin"]

PASSWORD = "Sturdy-passphrase-42"


@pytest.fixture(scope="session", autouse=True)
def backend_server(tmp_path_factory):
    work_dir = tmp_path_factory.mktemp("backend")
    (work_dir / "integration_settings.py").write_text(
        textwrap.dedent(
            f"""
            from coverworth_backend.settings import *  # noqa: F401,F403

            DATABASES = {{
                "default": {{
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": {str(work_dir / "db.sqlite3")!r},
                }}
            }}
            """
        )
    )

    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "integration_settings",
        "PYTHONPATH": os.pathsep.join([str(work_dir), str(BACKEND_DIR)]),
        "PYTHONIOENCODING": "utf-8",
    }
    log_file = open(work_dir / "server.log", "w", encoding="utf-8")

    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        check=True,
    )
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{BACKEND_PORT}", "--noreload"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    url = os.environ["BACKEND_URL"]
    deadline = time.monotonic() + 30
    while True:
        try:
            if requests.get(f"{url}/api/health/", timeout=1).ok:
                break
        except requests.RequestException:
            pass
        if server.poll() is not None or time.monotonic() > deadline:
            server.kill()
            log_file.close()
            raise RuntimeError(
                "Django test server did not start:\n"
                + (work_dir / "server.log").read_text(encoding="utf-8")
            )
        time.sleep(0.2)

    yield url

    server.terminate()
    server.wait(timeout=10)
    log_file.close()


class BackendApi:
    """Direct HTTP access to the test backend, for arranging and checking data."""

    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()

    def _headers(self):
        self.session.get(f"{self.url}/api/auth/csrf/", timeout=5)
        return {"X-CSRFToken": self.session.cookies.get("csrftoken", "")}

    def get(self, path, **kwargs):
        return self.session.get(f"{self.url}{path}", timeout=5, **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(f"{self.url}{path}", headers=self._headers(), timeout=5, **kwargs)

    def register(self, username: str):
        response = self.post(
            "/api/auth/register/",
            json={
                "first_name": "Test",
                "last_name": "User",
                "email": f"{username}@example.com",
                "username": username,
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def inventory_id(self) -> str:
        return self.get("/api/dashboard/").json()["inventory_id"]

    def create_category(self, name: str) -> dict:
        response = self.post(f"/api/inventory/{self.inventory_id()}/categories/", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["category"]

    def add_item(self, **fields) -> str:
        response = self.post(f"/api/inventory/{self.inventory_id()}/add-item/", data=fields)
        assert response.status_code == 200, response.text
        return response.json()["item_id"]


@pytest.fixture
def api(backend_server):
    return BackendApi(backend_server)


@pytest.fixture
def account(api):
    """A freshly registered user with an empty inventory."""
    username = f"user_{uuid.uuid4().hex[:10]}"
    api.register(username)
    return {"username": username, "password": PASSWORD}
