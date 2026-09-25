from pathlib import Path
import pandas as pd

GROUND_TRUTH = Path(__file__).parents[1] / "ground_truth" / "ground_truth.csv"


def load_ground_truth():
    df = pd.read_csv(GROUND_TRUTH)

    required_columns = {
        "item_name",
        "category",
        "condition",
        "reference_value",
        "source",
        "date_checked",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df


if __name__ == "__main__":
    df = load_ground_truth()

    print(df)
    print(f"\nLoaded {len(df)} ground-truth items.")