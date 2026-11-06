"""Serve private attachments through the signed-in NiceGUI session."""

from urllib.parse import urlparse
from uuid import UUID

import requests
from fastapi import Request
from nicegui import app, run
from starlette.responses import Response, StreamingResponse

import backend_client


class _AttachmentResponse(StreamingResponse):
    """Release the backend connection even if streaming fails or disconnects."""

    def __init__(self, content, *, headers, close):
        super().__init__(content, headers=headers)
        self._close_upstream = close

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._close_upstream()


def attachment_url(file_url: str | None) -> str:
    """Map an attachment API URL to this frontend's authenticated file route."""
    if not file_url:
        return ""
    parts = urlparse(file_url).path.split("/")
    if len(parts) != 6 or parts[1:3] != ["api", "attachment"] or parts[4:] != ["file", ""]:
        return ""
    try:
        attachment_id = UUID(parts[3])
    except (ValueError, AttributeError):
        return ""
    return f"/attachments/{attachment_id}"


async def serve_attachment(attachment_id: UUID, request: Request) -> Response:
    """Forward a file request using server-held cookies; Django checks ownership."""
    cookies = dict(app.storage.user.get("auth_cookies") or {})
    if not cookies:
        return Response("Authentication required.", status_code=401, media_type="text/plain")

    session = backend_client.authenticated_session(cookies)
    try:
        upstream = await run.io_bound(
            session.request,
            request.method,
            f"{backend_client.BACKEND_URL}/api/attachment/{attachment_id}/file/",
            timeout=10,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException:
        session.close()
        return Response("Could not load this attachment. Please try again.", status_code=502, media_type="text/plain")

    def close_upstream() -> None:
        upstream.close()
        session.close()

    if upstream.status_code != 200:
        status = upstream.status_code if upstream.status_code in {401, 403, 404} else 502
        close_upstream()
        return Response("Attachment unavailable.", status_code=status, media_type="text/plain")

    headers = {
        key: upstream.headers[key]
        for key in ("Content-Type", "Content-Disposition", "Content-Length")
        if key in upstream.headers
    }
    headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    if request.method == "HEAD":
        close_upstream()
        return Response(headers=headers)
    return _AttachmentResponse(
        upstream.iter_content(chunk_size=64 * 1024),
        headers=headers,
        close=close_upstream,
    )


def register_attachment_routes() -> None:
    """Also called after NiceGUI resets its routes between integration tests."""
    if not any(getattr(route, "name", None) == "private_attachment" for route in app.routes):
        app.api_route("/attachments/{attachment_id}", methods=["GET", "HEAD"], name="private_attachment")(serve_attachment)
