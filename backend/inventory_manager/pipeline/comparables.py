import re


ACCESSORY_OR_PART = re.compile(
    r"\b(?:replacement|compatible with|for parts|parts only|"
    r"blade only|stand|display case|box only|replica parts|bundle|"
    r"lot|hose|wand|dust cup|canister|floor nozzle|power head|motor base|motor body|filters?)\b"
)


def normalize_title(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def has_specific_identity(item_name, model_number=""):
    return bool(normalize_title(model_number)) or (
        len(set(normalize_title(item_name).split())) >= 4
    )

def select_name_matches(rows, item_name, *, brand="", model_number=""):
    name = normalize_title(item_name)
    model_words = set(normalize_title(model_number).split())
    required_words = set(name.split()) | set(normalize_title(brand).split())
    required_words |= model_words

    if not has_specific_identity(item_name, model_number):
        return []

    kept = []
    for row in rows:
        title = normalize_title(row.title)
        if not row.price.is_finite() or row.price <= 0:
            continue
        if ACCESSORY_OR_PART.search(title):
            continue

        if model_words:
            matches = required_words <= set(title.split())
        else:
            matches = f" {name} " in f" {title} "

        if matches:
            kept.append(row)

    return kept