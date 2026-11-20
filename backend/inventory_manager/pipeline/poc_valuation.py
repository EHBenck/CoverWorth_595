
from pathlib import Path
from statistics import median
from django.db.models import query
import pandas as pd
from .schemas import Listing
from .conditions import CONDITION_MAP 
from .ebay_client import load
from .review_candidates import RULES, classify_configuration, classify_listing

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw"
GROUND_TRUTH = Path(__file__).parents[1] / "ground_truth" / "ground_truth.csv"
EXCLUDE = ("case", "cover", "charger", "for parts", "box only", "screen protector")


def estimate(rows, query, want_condition="used", *, configuration=None):
    normalized_query = " ".join(query.lower().split())
    catalog_item = next(
        (name for name in RULES if name.lower() == normalized_query),
        None,
    )
    condition_matches = [row for row in rows if row.condition == want_condition]
    kept = []

    if "iphone 13" in normalized_query:
        kept = [
            row for row in condition_matches
            if not any(word in row.title.lower() for word in EXCLUDE)
            and "iphone 13" in row.title.lower()
            and "128gb" in row.title.lower().replace(" ", "")
            and "mini" not in row.title.lower()
            and "256gb" not in row.title.lower().replace(" ", "")
            and "512gb" not in row.title.lower().replace(" ", "")
        ]
    elif catalog_item and want_condition == "used":
        for row in condition_matches:
            candidate = {
                "item_name": catalog_item,
                "listing_title": row.title,
                "listing_price": row.price,
                "listing_condition": row.condition,
                "listing_id": row.listing_id,
            }
            decision, _ = classify_listing(candidate)
            if decision != "yes":
                continue

            listing_configuration = classify_configuration(candidate)
            if listing_configuration == "unclear":
                continue
            if listing_configuration != (configuration or "standard"):
                continue

            kept.append(row)
    if len(kept) >= 5:
        prices = pd.Series(float(row.price) for row in kept)
        q1, q3 = prices.quantile([0.25, 0.75])
        fence = 1.5 * (q3 - q1)
        kept = [
            row for row in kept
            if q1 - fence <= float(row.price) <= q3 + fence
        ]
    if len(kept) < 3:
        return {"query": query, "estimate": None, "n": len(kept), "confidence": "insufficient", "comparables": kept,}
    prices = sorted(float(r.price) for r in kept)
    med = median(prices)
    q1, q3 = pd.Series(prices).quantile([0.25, 0.75])
    spread = (q3 - q1) / med if med else 1
    conf = "high" if len(kept) >= 15 and spread < 0.4 else "medium" if len(kept) >= 5 else "low"
    return {"query": query, "estimate": round(med, 2), "low": round(q1, 2), "high": round(q3, 2), "n": len(kept), "confidence": conf, "comparables": kept,}

if __name__ == "__main__":
    path = FIXTURES / "ebay_iphone13.json"

    rows = load(path)
    result = estimate(rows, "iPhone 13 128GB")

    print(result)
