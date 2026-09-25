
from pathlib import Path
from statistics import median
import pandas as pd
from schemas import Listing
from conditions import CONDITION_MAP
from ebay_client import load

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw"
GROUND_TRUTH = Path(__file__).parents[1] / "ground_truth" / "ground_truth.csv"
EXCLUDE = ("case", "cover", "charger", "for parts", "box only", "screen protector")


def estimate(rows, query, want_condition="used"):
    kept = [r for r in rows if r.condition == want_condition]
   
    kept = [r for r in kept if not any(w in r.title.lower() for w in EXCLUDE)]
    kept = [
        r for r in kept
        if "iphone 13" in r.title.lower()
        and "128gb" in r.title.lower().replace(" ", "")
        and "mini" not in r.title.lower()
        and "256gb" not in r.title.lower().replace(" ", "")
        and "512gb" not in r.title.lower().replace(" ", "")
    ]
    if len(kept) < 3:
        return {"query": query, "estimate": None, "n": len(kept), "confidence": "insufficient"}
    prices = sorted(float(r.price) for r in kept)
    med = median(prices)
    q1, q3 = pd.Series(prices).quantile([0.25, 0.75])
    spread = (q3 - q1) / med if med else 1
    conf = "high" if len(kept) >= 15 and spread < 0.4 else "medium" if len(kept) >= 5 else "low"
    return {"query": query, "estimate": round(med, 2), "low": round(q1, 2),
            "high": round(q3, 2), "n": len(kept), "confidence": conf}

if __name__ == "__main__":
    path = FIXTURES / "ebay_iphone13.json"

    rows = load(path)
    result = estimate(rows, "iPhone 13 128GB")

    print(result)
