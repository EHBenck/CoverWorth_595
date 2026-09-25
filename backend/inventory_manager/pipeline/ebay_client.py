import json
from decimal import Decimal
from schemas import Listing
from conditions import CONDITION_MAP

def load(path):
    data = json.loads(path.read_text())
    rows = []
    for s in data.get("itemSummaries", []):
        price = s.get("price", {})
        if price.get("currency") != "USD":
            continue
        if "FIXED_PRICE" not in s.get("buyingOptions", []):
            continue  # skip auctions
        rows.append(
            Listing(
                title=s["title"],
                price=Decimal(price["value"]),   # value is a string
                condition=CONDITION_MAP.get(s.get("conditionId")),
            )
        )
    return rows