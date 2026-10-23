"""Stand-in for the eBay API inside the test Django server.

conftest.py loads this from the throwaway integration settings, so it runs
in the server process. Only eBay's HTTP layer is replaced: the real
search_ebay() parsing and estimate() pipeline still run, against the
recorded listings in backend/inventory_manager/fixtures/raw.

Items whose name contains EBAY_DOWN make eBay unreachable.
"""

from pathlib import Path
from types import SimpleNamespace

import requests

EBAY_DOWN = "ebay-down"

# Result of estimate() on the fixture for a used item.
FIXTURE_ESTIMATE = 247.0

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "backend" / "inventory_manager" / "fixtures" / "raw" / "ebay_iphone13.json"
)


def _search(url, params=None, **kwargs):
    if EBAY_DOWN in params["q"]:
        raise requests.ConnectionError("eBay is unreachable")

    response = requests.Response()
    response.status_code = 200
    response.url = url
    response._content = FIXTURE.read_bytes()
    return response


def install():
    from inventory_manager.pipeline import ebay_client

    ebay_client.get_ebay_access_token = lambda: "test-token"
    ebay_client.requests = SimpleNamespace(get=_search)

