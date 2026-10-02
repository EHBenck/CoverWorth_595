import os
from urllib.parse import urlparse

import requests
from nicegui import app


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def authenticated_session(cookies=None) -> requests.Session:
    session = requests.Session()
    cookie_domain = urlparse(BACKEND_URL).hostname
    stored_cookies = cookies or app.storage.user.get("auth_cookies", {})
    for name, value in stored_cookies.items():
        session.cookies.set(name, value, domain=cookie_domain, path="/")
    return session


def csrf_headers(session: requests.Session) -> dict[str, str]:
    response = session.get(f"{BACKEND_URL}/api/auth/csrf/", timeout=5)
    response.raise_for_status()
    token = response.cookies.get("csrftoken")
    if token is None:
        token = session.cookies.get_dict().get("csrftoken", "")
    return {"X-CSRFToken": token}