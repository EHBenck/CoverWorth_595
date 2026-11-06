"""Manual live eBay check. Run with: python -m inventory_manager.pipeline.test_live

The guard keeps the test runner from calling the real eBay API when it
imports this module during discovery.
"""

from .ebay_client import search_ebay
from .poc_valuation import estimate

if __name__ == "__main__":
    queries = [
        "Dell XPS 13 9310 i7-1185G7 16GB 512GB",
        "Dyson V8 Absolute cordless vacuum",
        "Milwaukee 2767-20 impact wrench tool only",
    ]

    for query in queries:
        rows = search_ebay(query, used_only=True)
        used = [row for row in rows if row.condition == "used"]

        print(f"\n{query}")
        print(f"Retrieved: {len(rows)}")
        print(f"Used listings: {len(used)}")

        for row in used[:5]:
            print(f"${row.price} - {row.title}")
