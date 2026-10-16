from .ebay_client import search_ebay
from .poc_valuation import estimate

query = "iPhone 13 128GB"

rows = search_ebay(query)
print(f"Retrieved {len(rows)} listings")

result = estimate(rows, query)
print(result)
