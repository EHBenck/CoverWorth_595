
from pathlib import Path
from statistics import median
from django.db.models import query
import pandas as pd
from .schemas import Listing
from .conditions import CONDITION_MAP 
from .ebay_client import load
import re

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw"
GROUND_TRUTH = Path(__file__).parents[1] / "ground_truth" / "ground_truth.csv"
EXCLUDE = ("case", "cover", "charger", "for parts", "box only", "screen protector")

def normalize_text(text):
        text = text.lower()
        text = re.sub(r"(\d+)\s+(gb|tb)", r"\1\2", text)
        return text

def matches_storage(query, title):
    query_storage = set(
        re.findall(r"\b\d+(?:gb|tb)\b", normalize_text(query))
    )

    title_storage = set(
        re.findall(r"\b\d+(?:gb|tb)\b", normalize_text(title))
    )

    if not query_storage:
        return True

    return title_storage == query_storage

def matches_variant(query, title):
    variants = ("mini", "pro", "max", "plus", "ultra")

    query_words = set(normalize_text(query).split())
    title_words = set(normalize_text(title).split())

    for variant in variants:
        if variant in title_words and variant not in query_words:
            return False

    return True

def estimate(rows, query, want_condition="used"):
    kept = [r for r in rows if r.condition == want_condition]
   
    kept = [r for r in kept if not any(w in r.title.lower() for w in EXCLUDE)]
    import re

    query_words = normalize_text(query).split()

    kept = [
        r for r in kept
        if all(word in normalize_text(r.title) for word in query_words)
        and matches_storage(query, r.title)
        and matches_variant(query, r.title)
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
