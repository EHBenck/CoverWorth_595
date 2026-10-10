import os

from .ebay_client import search_ebay
from .poc_valuation import estimate

token = os.getenv("EBAY_ACCESS_TOKEN")
if not token:
    raise RuntimeError("EBAY_ACCESS_TOKEN is not set")
rows = search_ebay("iPhone 13 128GB", token)
print(f"Retrieved {len(rows)} listings")
result = estimate(rows, "iPhone 13 128GB")
print(result)