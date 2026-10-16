import json
from decimal import Decimal
from .schemas import Listing
from .conditions import CONDITION_MAP
import requests
import os
import time

def parse_listings(data):
    rows = []
    summaries = data.get("itemSummaries", [])
    for s in summaries:
        price = s.get("price", {})
        if price.get("currency") != "USD":
            continue
        if "FIXED_PRICE" not in s.get("buyingOptions", []):
            continue
        rows.append(
            Listing(
                title=s["title"],
                price=Decimal(price["value"]),
                condition=CONDITION_MAP.get(s.get("conditionId")),
            )
        )
    return rows

def load(path):
    data = json.loads(path.read_text())
    return parse_listings(data)

# Cached eBay application token
_cached_token = None
_token_expires_at = 0


def get_ebay_access_token():
    global _cached_token, _token_expires_at

    # Reuse the token if it has not expired
    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError("Missing eBay credentials in environment variables.")

    token_url = "https://api.ebay.com/identity/v1/oauth2/token"

    response = requests.post(
        token_url,
        auth=(client_id, client_secret),
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        },
        timeout=15,
    )

    response.raise_for_status()
    token_data = response.json()

    _cached_token = token_data["access_token"]

    # Refresh one minute before expiration
    _token_expires_at = (
        time.time() + int(token_data["expires_in"]) - 60
    )

    return _cached_token

def search_ebay(query, access_token=None):
    if access_token is None:
        access_token = get_ebay_access_token()

    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    params = {
        "q": query,
        "limit": 50,        
        "filter": "buyingOptions:{FIXED_PRICE}",
    }
    response = requests.get(url, headers=headers, params=params, timeout=15,)
    response.raise_for_status()
    data = response.json() 
    rows = parse_listings(data)
    return rows