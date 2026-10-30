"""Manual live eBay benchmark.

Run with:
python -m inventory_manager.pipeline.test_live
"""

from dotenv import load_dotenv
load_dotenv()
from .ebay_client import search_ebay
from .poc_valuation import estimate


if __name__ == "__main__":
    queries = [
        "iPhone 13 128GB",
        "Samsung Galaxy S22 128GB",
        "Nintendo Switch OLED",
        "Sony WH-1000XM5",
        "Canon EOS Rebel T7",
    ]

    for query in queries:
        print(f"\nTesting: {query}")

        try:
            rows = search_ebay(query)
            result = estimate(rows, query)

            print(f"Retrieved: {len(rows)} listings")
            print(f"Comparables: {result['n']}")
            print(f"Estimate: ${result['estimate']}")
            print(f"Confidence: {result['confidence']}")

        except Exception as e:
            print(f"Error: {e}")
