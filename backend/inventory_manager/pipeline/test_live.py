"""Manual live eBay check. Run with: python -m inventory_manager.pipeline.test_live

The guard keeps the test runner from calling the real eBay API when it
imports this module during discovery.
"""

from .ebay_client import search_ebay
from .poc_valuation import estimate

if __name__ == "__main__":
    query = "iPhone 13 128GB"

    rows = search_ebay(query)
    print(f"Retrieved {len(rows)} listings")

    result = estimate(rows, query)
    print(result)
