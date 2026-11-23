
from pathlib import Path
from statistics import median
from django.db.models import query
import pandas as pd
from .schemas import Listing
from .conditions import CONDITION_MAP 
from .ebay_client import load
from .review_candidates import RULES, classify_configuration, classify_listing
from .comparables import has_specific_identity, select_name_matches

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw"
GROUND_TRUTH = Path(__file__).parents[1] / "ground_truth" / "ground_truth.csv"
EXCLUDE = ("case", "cover", "charger", "for parts", "box only", "screen protector")
MIN_COMPARABLES = 3

def estimate(rows, query, want_condition="used", *, configuration=None, item_name=None, brand="", model_number="",):
    normalized_query = " ".join(query.lower().split())
    normalized_item_name = " ".join((item_name or query).lower().split())
    catalog_item = next(
        (name for name in RULES if name.lower() == normalized_item_name),
        None,
    )
    condition_matches = [row for row in rows if row.condition == want_condition]
    kept = []
    needs_item_details = False

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
    elif catalog_item is None and want_condition == "used":
        fallback_name = item_name or query
        needs_item_details = not has_specific_identity(fallback_name, model_number)
        kept = select_name_matches(
            condition_matches,
            fallback_name,
            brand=brand,
            model_number=model_number,
        )
    if len(kept) >= 5:
        prices = pd.Series(float(row.price) for row in kept)
        q1, q3 = prices.quantile([0.25, 0.75])
        fence = 1.5 * (q3 - q1)
        kept = [
            row for row in kept
            if q1 - fence <= float(row.price) <= q3 + fence
        ]
    if len(kept) < MIN_COMPARABLES:
        if needs_item_details:
            message = "Add a brand and model number, or enter a more specific item name."
        else:
            count = len(kept)
            noun = "listing" if count == 1 else "listings"
            message = (
                f"Found {count} matching {want_condition} {noun}. "
                f"At least {MIN_COMPARABLES} are needed for an estimate."
            )

        return {
            "query": query,
            "estimate": None,
            "n": len(kept),
            "confidence": "insufficient",
            "comparables": kept,
            "message": message,
        }
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
