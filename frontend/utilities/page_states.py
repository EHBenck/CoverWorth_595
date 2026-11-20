"""Shared empty, error, and session-expired states for every signed-in page.

Pages keep their own layout; these helpers only make "nothing here yet" and
"something went wrong" look and read the same everywhere.
"""

from collections.abc import Callable

import requests
from nicegui import app, ui


# MESSAGES
# ============================================================
SESSION_EXPIRED = "Your session expired. Please sign in again."
BACKEND_UNAVAILABLE = (
    "CoverWorth can't reach the server right now. "
    "Check your connection and try again."
)
VALUATION_UNAVAILABLE = (
    "Live pricing from eBay is unavailable right now. Please try again later."
)
NOT_ENOUGH_COMPARABLES = (
    "Not enough comparable listings were found to estimate a value. "
    "Adding a brand or model number can help."
)


def load_failed(what: str) -> str:
    return f"Could not load {what}. Please try again."


def request_failed(what: str, error: Exception) -> str:
    """Name the cause users can act on: no connection vs. the request failing."""
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return BACKEND_UNAVAILABLE
    return load_failed(what)


# ERRORS RAISED BY PAGE LOADERS
# ============================================================
class PageLoadError(Exception):
    """A page could not load its data; the message is safe to show."""


class SessionExpired(PageLoadError):
    """Django no longer recognizes this browser's login."""

    def __init__(self, message: str = SESSION_EXPIRED):
        super().__init__(message)


# SESSION
# ============================================================
def end_session(message: str = SESSION_EXPIRED) -> None:
    """Forget this browser's login and show the reason on the sign-in page."""
    app.storage.user.pop("auth_cookies", None)
    app.storage.user.pop("username", None)
    app.storage.user["login_message"] = message
    ui.navigate.to("/")


# STATES
# ============================================================
def show_empty_state(
    icon: str,
    title: str,
    description: str,
    *,
    action_label: str | None = None,
    action_icon: str | None = None,
    on_action: Callable | None = None,
    padding: str = "py-16",
) -> ui.column:
    """Nothing to show yet, optionally with the one action that fixes it."""
    with ui.column().classes(
        f"w-full items-center justify-center text-center {padding} gap-2"
    ).mark("empty-state") as state:
        ui.icon(icon).classes("text-5xl text-slate-300")
        ui.label(title).classes("text-lg font-semibold text-slate-600")
        ui.label(description).classes("text-sm muted")
        if action_label and on_action:
            ui.button(action_label, icon=action_icon, on_click=on_action).props(
                "unelevated color=primary no-caps"
            ).classes("mt-2")
    return state


def show_item_not_found() -> None:
    """A missing, archived, malformed, or someone else's item all read the same."""
    with ui.column().classes("page-content-frame p-7"):
        show_empty_state(
            "inventory_2",
            "Item not found",
            "This item may have been deleted or archived, or it belongs to another account.",
            action_label="Back to Inventory",
            action_icon="arrow_back",
            on_action=lambda: ui.navigate.to("/inventory"),
        )


def show_error_state(
    message: str,
    *,
    title: str = "Something went wrong",
    on_retry: Callable | None = None,
    padding: str = "py-16",
) -> ui.column:
    """Loading failed. Retry reloads the page unless a handler is given."""
    with ui.column().classes(
        f"w-full items-center justify-center text-center {padding} gap-2"
    ).mark("error-state") as state:
        ui.icon("cloud_off").classes("text-5xl text-red-300")
        ui.label(title).classes("text-lg font-semibold text-slate-700")
        ui.label(message).classes("text-sm muted").props("role=alert")
        ui.button(
            "Try again",
            icon="refresh",
            on_click=on_retry or ui.navigate.reload,
        ).props("outline color=primary no-caps").classes("mt-2")
    return state
