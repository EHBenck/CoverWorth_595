"""Collect eBay listings for independent ground truth review.

Run from backend:
python -m inventory_manager.pipeline.collect_ground_truth
"""

import csv
from datetime import date
from pathlib import Path
from statistics import median

from dotenv import load_dotenv

from .ebay_client import search_ebay

load_dotenv()

BASE = Path(__file__).resolve().parents[1]
GROUND_TRUTH = BASE / "ground_truth" / "ground_truth.csv"
OUTPUT = BASE / "ground_truth" / "ground_truth_candidates.csv"


def collect():
    with GROUND_TRUTH.open(newline="", encoding="utf-8-sig") as file:
        products = list(csv.DictReader(file))

    candidates = []

    for product in products:
        query = product["item_name"]

        print(f"Collecting: {query}")

        try:
            listings = search_ebay(query)

            for listing in listings:
                candidates.append({
                    "item_name": query,
                    "category": product["category"],
                    "condition": product["condition"],
                    "listing_title": listing.title,
                    "listing_price": listing.price,
                    "listing_condition": listing.condition,
                    "listing_id": listing.listing_id,
                    "listing_url": listing.url,
                    "include": "",
                    "date_checked": date.today().isoformat(),
                })

            print(f"  Retrieved {len(listings)} candidates")

        except Exception as error:
            print(f"  Error: {error}")

    if not candidates:
        print("No candidates collected.")
        return

    if OUTPUT.exists():
        raise FileExistsError(
            f"{OUTPUT} already exists. Rename or archive it before collecting again."
    )

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=candidates[0].keys())
        writer.writeheader()
        writer.writerows(candidates)

    print(f"\nSaved candidates to: {OUTPUT}")


if __name__ == "__main__":
    collect()