"""Global item search backed by the Django API, scoped to the active inventory."""

import requests

from backend_client import BACKEND_URL, authenticated_session
from utilities.inventory_switcher import InventoryApiError, _api_error

# TODO: set this to the URL your Inventory page already uses for Django's
# item_list view (I couldn't see urls.py).
ITEMS_ENDPOINT = "/api/items/"
RESULT_LIMIT = 8


class SearchSessionExpired(InventoryApiError):
    """The Django login session no longer exists."""


def search_items(cookies: dict, query: str) -> tuple[list[dict], dict]:
    """Search items in the user's active inventory.

    Runs in a worker thread (run.io_bound), so it must not touch app.storage.
    Pass the auth cookies in and use the refreshed cookies it returns.

    Django's item_list view already filters to the session's active inventory
    and (with the q/limit patch) matches name, brand, model, serial number,
    category and location. Response shape:
        {"items": [{"public_id", "name", "category", "location", ...}, ...]}
    """
    with authenticated_session(cookies) as session:
        response = session.get(
            f"{BACKEND_URL}{ITEMS_ENDPOINT}",
            params={"q": query, "limit": RESULT_LIMIT},
            timeout=10,
        )
        if response.status_code == 401:
            raise SearchSessionExpired("Your session expired. Please sign in again.")
        if not response.ok:
            raise InventoryApiError(_api_error(response))
        result = response.json()
        if not isinstance(result, dict):
            raise InventoryApiError("The server returned an unexpected response. Try again.")
        return result.get("items", []), session.cookies.get_dict()
