from pathlib import Path
from datetime import date
import shutil
import pandas as pd

DATA_DIR = Path(__file__).parents[1] / "ground_truth"

ground_truth_path = DATA_DIR / "ground_truth.csv"
reference_path = DATA_DIR / "ground_truth_reference_values.csv"
backup_path = DATA_DIR / "ground_truth_before_medians_backup.csv"

ground_truth = pd.read_csv(ground_truth_path, dtype=str).fillna("")
references = pd.read_csv(reference_path, dtype=str).fillna("")

# Back up before making changes
if not backup_path.exists():
    shutil.copy2(ground_truth_path, backup_path)

# Match standard product reference values
standard = references[
    (references["configuration"] == "standard")
    & (references["status"] == "provisional")
].set_index("item_name")

ground_truth["configuration"] = "standard"

milwaukee_name = 'Milwaukee M18 Fuel 1/2" Impact Wrench'

for index, row in ground_truth.iterrows():
    item = row["item_name"]

    if item in standard.index:
        ground_truth.at[index, "reference_value"] = standard.at[item, "median"]
        ground_truth.at[index, "date_checked"] = date.today().isoformat()

# Remove existing Milwaukee rows so reruns don't create duplicates
milwaukee_rows = ground_truth[
    ground_truth["item_name"] == milwaukee_name
]

if len(milwaukee_rows) == 0:
    raise ValueError("Milwaukee product not found in ground truth CSV")

milwaukee_template = milwaukee_rows.iloc[0].copy()

ground_truth = ground_truth[
    ground_truth["item_name"] != milwaukee_name
].copy()

new_rows = []

for configuration in ["kit", "tool_only"]:
    match = references[
        (references["item_name"] == milwaukee_name)
        & (references["configuration"] == configuration)
        & (references["status"] == "provisional")
    ]

    if len(match) != 1:
        raise ValueError(f"Expected one Milwaukee {configuration} reference value")

    new_row = milwaukee_template.copy()
    new_row["configuration"] = configuration
    new_row["reference_value"] = match.iloc[0]["median"]
    new_row["date_checked"] = date.today().isoformat()

    new_rows.append(new_row)

ground_truth = pd.concat(
    [ground_truth, pd.DataFrame(new_rows)],
    ignore_index=True
)

ground_truth.to_csv(ground_truth_path, index=False)

print(f"Updated {len(ground_truth)} ground-truth rows.")
print(ground_truth[
    ground_truth["item_name"] == milwaukee_name
][["item_name", "configuration", "reference_value"]])