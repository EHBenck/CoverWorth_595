import csv
from collections import defaultdict
from decimal import Decimal
from statistics import mean

from inventory_manager.pipeline.ground_truth import GROUND_TRUTH, load_ground_truth
from inventory_manager.pipeline.poc_valuation import estimate
from inventory_manager.pipeline.schemas import Listing

listings = defaultdict(list)
archive = GROUND_TRUTH.with_name("ground_truth_candidates_expanded.csv")
with archive.open(encoding="utf-8-sig", newline="") as file:
    for row in csv.DictReader(file):
        listings[row["item_name"]].append(Listing(
            title=row["listing_title"],
            price=Decimal(row["listing_price"]),
            condition=row["listing_condition"],
            listing_id=row["listing_id"],
            url=row["listing_url"],
        ))

references = load_ground_truth()
errors = []
percentage_errors = []

for row in references.itertuples(index=False):
    result = estimate(
        listings[row.item_name],
        row.item_name,
        row.condition.lower(),
        configuration=row.configuration,
    )
    label = f"{row.item_name} [{row.configuration}]"
    value = result["estimate"]
    if value is None:
        print(f"{label}: no estimate ({result['n']} comparables)")
        continue

    error = abs(value - row.reference_value)
    errors.append(error)
    percentage_errors.append(100 * error / row.reference_value)
    print(
        f"{label}: {result['n']} comparables, "
        f"estimate=${value:.2f}, reference=${row.reference_value:.2f}, "
        f"absolute error=${error:.2f}"
    )

print(f"\nCoverage: {len(errors)}/{len(references)}")
if errors:
    print(f"MAE: ${mean(errors):.2f}")
    print(f"MAPE: {mean(percentage_errors):.2f}%")
