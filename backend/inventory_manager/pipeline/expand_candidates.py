
from pathlib import Path
from datetime import date
import pandas as pd

from .ebay_client import search_ebay

DATA_DIR = Path(__file__).resolve().parents[1] / "ground_truth"

SOURCE = DATA_DIR / "ground_truth_candidates.csv"
OUTPUT = DATA_DIR / "ground_truth_candidates_expanded.csv"

SEARCHES = {
    "Dell XPS 13 9310": "Dell XPS 13 9310 i7-1185G7 16GB 512GB",
    "Dyson V8 Absolute": "Dyson V8 Absolute cordless vacuum",
    'Milwaukee M18 Fuel 1/2" Impact Wrench':
        "Milwaukee 2767-20 impact wrench tool only",
}


def main():
    original = pd.read_csv(SOURCE, dtype={"listing_id": str})
    new_rows = []

    for item, query in SEARCHES.items():
        listings = search_ebay(query, used_only=True)

        print(f"{item}: retrieved {len(listings)} listings")

        category = original.loc[
            original["item_name"] == item, "category"
        ].iloc[0]

        for listing in listings:
            if listing.condition != "used":
                continue

            new_rows.append({
                "item_name": item,
                "category": category,
                "condition": "used",
                "listing_title": listing.title,
                "listing_price": float(listing.price),
                "listing_condition": listing.condition,
                "listing_id": listing.listing_id,
                "listing_url": listing.url,
                "include": "review",
                "date_checked": date.today().isoformat(),
            })

    additions = pd.DataFrame(new_rows, columns=original.columns)

    expanded = pd.concat(
        [original, additions],
        ignore_index=True
    )

    expanded = expanded.drop_duplicates(
        subset=["item_name", "listing_id"],
        keep="first"
    )

    expanded.to_csv(OUTPUT, index=False)

    print(f"\nOriginal listings: {len(original)}")
    print(f"New unique listings: {len(expanded) - len(original)}")
    print(f"Expanded dataset: {len(expanded)}")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
