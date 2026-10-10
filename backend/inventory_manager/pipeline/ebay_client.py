import json
from decimal import Decimal
from .schemas import Listing
from .conditions import CONDITION_MAP
import requests

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

def search_ebay(query, access_token):
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }
    params = {
        "q": query,
        "limit": 50,        "filter": "buyingOptions:{FIXED_PRICE}",
    }
    response = requests.get(url, headers=headers, params=params, timeout=15,)
    response.raise_for_status()
    data = response.json() 
    rows = parse_listings(data)
    return rows