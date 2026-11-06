
import pandas as pd
import re
from pathlib import Path

DATA_DIR = Path(__file__).parents[1] / "ground_truth"
CANDIDATES = DATA_DIR / "ground_truth_candidates_expanded.csv"

# Each target has a required identity pattern and optional exclusions.
# Ambiguous configurations are flagged for review, not accepted.
RULES = {
    "Apple iPhone 13 128GB": (r"\biphone\s*13\b", r"\bmini\b|\bpro\b"),
    "Apple iPhone 14 128GB": (r"\biphone\s*14\b", r"\bplus\b|\bpro\b"),
    "Samsung Galaxy S22 128GB": (r"\b(?:galaxy\s*)?s22\b", r"\bultra\b|\bplus\b|\bs22\+\b"),
    "Apple iPad 10th Gen 64GB": (r"\bipad\b", r"\bmini\b|\bair\b|\bpro\b"),
    "Apple Watch Series 8 45mm": (r"\b(?:apple\s*)?watch\b.*\b(?:series\s*8|s8)\b", r"\bultra\b|\bse\b"),
    "Nintendo Switch OLED": (r"\bswitch\b.*\boled\b", r"\blite\b"),
    "Sony PlayStation 5 Disc Edition": (r"\b(?:playstation\s*5|ps5)\b", r"\bdigital\s*edition\b"),
    "Xbox Series X 1TB": (r"\bxbox\b.*\bseries\s*x\b", r"\bseries\s*s\b"),
    "Nintendo Switch Lite": (r"\bswitch\s*lite\b", r"\boled\b"),
    "Sony WH-1000XM5": (r"\bwh[\s-]?1000xm5\b", r"\bwh[\s-]?1000xm4\b"),
    "Apple AirPods Max": (r"\bairpods\s*max\b", r""),
    "Bose QuietComfort 45": (r"\b(?:quietcomfort\s*45|qc45)\b", r""),
    "Canon EOS Rebel T7": (r"\b(?:rebel\s*t7|eos\s*2000d)\b", r"\bt7i\b"),
    "GoPro HERO11 Black": (r"\bhero\s*11\b|\bhero11\b", r"\bmini\b"),
    "Apple MacBook Air M1 2020 256GB": (r"\bmacbook\s*air\b", r"\bmacbook\s*pro\b"),
    "Dell XPS 13 9310": (r"\bxps\s*13\s*9310\b", r""),
    "Dyson V8 Absolute": (r"\bdyson\b.*\bv8\b.*\babsolute\b", r"\borigin\b|\bslim\b"),
    "KitchenAid Artisan 5-Quart Stand Mixer": (r"\bkitchenaid\b.*\bartisan\b", r""),
    'Milwaukee M18 Fuel 1/2" Impact Wrench': (r"\bmilwaukee\b.*\bm18\b.*\bfuel\b", r"\bimpact\s*driver\b"),
    "LEGO Star Wars Millennium Falcon 75257": (r"\b75257\b", r""),
}

STORAGE_TARGETS = {
    "Apple iPhone 13 128GB": 128,
    "Apple iPhone 14 128GB": 128,
    "Samsung Galaxy S22 128GB": 128,
    "Apple iPad 10th Gen 64GB": 64,
    "Apple MacBook Air M1 2020 256GB": 256,
    "Xbox Series X 1TB": 1024,
}

def storage_values(title):
    title = title.lower()
    values = set()

    # Remove RAM specifications before detecting storage capacities.
    title = re.sub(
        r"\b\d+\s*(?:gb|tb)\s*ram\b",
        "",
        title,
        flags=re.IGNORECASE
    )

    title = re.sub(
        r"\bram\s*[:\-]?\s*\d+\s*(?:gb|tb)\b",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Match explicitly labeled storage capacities.
    for number, unit in re.findall(r"\b(\d+)\s*(gb|tb)\b", title):
        value = int(number) * (1024 if unit == "tb" else 1)
        values.add(value)

    # Match lists such as 128/256/512GB.
    for match in re.finditer(
        r"\b(?:\d{2,4}\s*[/|]\s*)+\d{2,4}\s*(?:gb|tb)\b",
        title
    ):
        text = match.group()
        unit = "tb" if text.endswith("tb") else "gb"

        for number in re.findall(r"\d+", text):
            values.add(int(number) * (1024 if unit == "tb" else 1))

    return values

def classify_bundle(item, title):
    title = title.lower()

    # Reject clearly enhanced bundles across all products.
    if re.search(
        r"\bextra controllers?\b|"
        r"\b[2-9]\s*(?:dualsense\s+)?controllers?\b|"
        r"\bwith games?\b|"
        r"\b[2-9]\s*(?:sealed\s*)?games?\b",
        title
    ):
        return "no", "enhanced_bundle"

    # Reject additional games and upgraded controllers.
    if item in (
        "Sony PlayStation 5 Disc Edition",
        "Xbox Series X 1TB"
    ):
        if re.search(
            r"\+\s*(?:gta\s*5|.*\bnew game\b)|"
            r"\bcontroller\s*(?:&|and)\s*game\b|"
            r"\bpro controller\b",
            title
        ):
            return "no", "enhanced_bundle"

    # Nintendo Switch bundles.
    if item.startswith("Nintendo Switch"):
        if re.search(
            r"\bpro controller\b|"
            r"\bspongebob\b|"
            r"\banimal crossing\b|"
            r"\bscreen protector\b.*\bsd card\b",
            title
        ):
            return "no", "enhanced_bundle"

        if item == "Nintendo Switch OLED" and "splatoon 3 edition" in title:
            return "no", "special_edition"

    # PS5 bundles.
    if item == "Sony PlayStation 5 Disc Edition":
        if re.search(r"\bslim\b|\bcfi-20\d{2}\b", title):
            return "no", "wrong_model"

        if re.search(
            r"\belite headset\b|"
            r"\b1\s*tb\s*ssd\b",
            title
        ):
            return "no", "enhanced_bundle"

   # Canon camera bundles with additional lenses.
    if item == "Canon EOS Rebel T7":
        if re.search(
            r"\b(?:75|70)\s*-\s*300(?:\s*mm)?\b|"
            r"\b420\s*-\s*800(?:\s*mm)?\b|"
            r"\b50\s*mm\b",
            title
        ):
            return "no", "enhanced_bundle"

    # Reject PS5 bundles containing additional games.
    if item == "Sony PlayStation 5 Disc Edition":
        if re.search(r"\bgod of war\b", title):
            return "no", "enhanced_bundle"

    # Reject GoPro bundles advertising additional accessories.
    if item == "GoPro HERO11 Black":
        if re.search(
            r"\baccessories bundle\b|"
            r"\bwith accessories\b|"
            r"\bwaterproof case\b|"
            r"\bextra batteries\b|"
            r"\bbatteries\s+and\s+extra\b",
            title
        ):
            return "no", "enhanced_bundle"

    # Keep unspecified bundles for manual review.
    if re.search(
        r"\bbundle\b|\bbundled\b|\bwith accessories\b",
        title
    ):
        return "review", "bundle_uncertain"

    return None

def classify_listing(row):
    item = str(row["item_name"])
    title = str(row["listing_title"]).lower()
    condition = str(row["listing_condition"]).lower().strip()

    try:
        price = float(row["listing_price"])
    except (TypeError, ValueError):
        return "no", "invalid_price"

    if not pd.notna(price) or price <= 0:
        return "no", "invalid_price"

    if condition != "used":
        return "no", "condition_mismatch"

    if item not in RULES:
        return "review", "unknown_product"

    required, excluded = RULES[item]
    if not re.search(required, title):
        return "no", "model_mismatch"

    if excluded and re.search(excluded, title):
        return "no", "wrong_variant"

    if re.search(
        r"\b(for parts|parts only|not working|broken|"
        r"motherboard|replacement parts?|replacement head|"
        r"vacuum head|floor tool|motorhead only|"
        r"box only|case only)\b",
        title
    ):
        return "no", "parts_or_accessory"

    if item == "Dyson V8 Absolute":
        if re.search(r"\bscratch\s*(?:&|and)\s*dent\b|\bdemo model\b", title):
            return "no", "condition_mismatch"

    if item == "Dyson V8 Absolute":
        if re.search(r"\bscratch\s*(?:&|and)\s*dent\b|\bdemo model\b", title):
            return "review", "condition_uncertain"

    if item == "Samsung Galaxy S22 128GB":
        if re.search(
            r"\bs22\s*\+|\bs22\s*plus\b|\bs22\s*ultra\b|"
            r"\bsm-s90[68]\w*\b",
            title
        ):
            return "no", "wrong_model"

    if item == "Sony PlayStation 5 Disc Edition":
        if re.search(r"\bcfi-1015a\b", title) and re.search(r"\b1\s*tb\b", title):
            return "no", "storage_mismatch"

    if item == "Xbox Series X 1TB":
        if re.search(r"\b4\s+games\b", title):
            return "no", "enhanced_bundle"

    if item in STORAGE_TARGETS:
        capacities = storage_values(title)

    # MacBook listings contain both RAM and SSD capacities.
    # Only consider storage values, not RAM.
        if item == "Apple MacBook Air M1 2020 256GB":
            capacities = {
                value for value in capacities
                if value >= 128
            }
        target = STORAGE_TARGETS[item]

        if capacities and target not in capacities:
            return "no", "wrong_storage"
        if not capacities:
            return "review", "storage_uncertain"
        if len(capacities) > 1:
            return "no", "multiple_storage_options"

    if item == "Apple Watch Series 8 45mm":
        if re.search(r"\b41\s*mm\b", title):
            return "no", "wrong_size"
        if not re.search(r"\b45\s*mm\b", title):
            return "review", "size_uncertain"

    if item == "Apple iPad 10th Gen 64GB":
        if re.search(r"\bcellular\b", title):
            return "no", "different_connectivity"

        if not re.search(r"\b10th\b|\b10\.9\b|\b2022\b", title):
            return "review", "generation_uncertain"

    if item == "Apple MacBook Air M1 2020 256GB":
        if not re.search(r"\bm1\b|\ba2337\b", title):
            return "no", "wrong_processor"

    if item == "Apple MacBook Air M1 2020 256GB":
        if re.search(r"\b16\s*gb\b", title):
            return "no", "different_ram_configuration"

    if item == "Sony PlayStation 5 Disc Edition":
        if not re.search(r"\bdisc\b|\bdisk\b|\bcfi-\d{4}a\b", title):
            return "review", "edition_uncertain"

    # Reject refurbished or visibly damaged products.
    if re.search(
        r"\b(refurbished|grade d|cracked|screen burn)\b",
        title
    ):
        return "no", "condition_mismatch"

    # Keep ambiguous condition descriptions for manual review.
    if re.search(
        r"\b(prepaid|untested|read description)\b",
        title
    ):
        return "review", "condition_uncertain"

    bundle_result = classify_bundle(item, title)

    if bundle_result is not None:
        return bundle_result

    if item.startswith(("Apple iPhone", "Samsung Galaxy")):
    # Reject explicitly carrier-locked phones.
        if re.search(
            r"\b(at&t only|att only|carrier locked|locked to|"
            r"verizon only|t-mobile only|tmobile only)\b",
            title
        ):
            return "no", "carrier_locked"

        # Reject carrier-specific phones unless explicitly unlocked.
        if re.search(
            r"\b(verizon|tmobile|t-mobile|at&t|att carrier|prepaid)\b",
            title
        ):
            if not re.search(r"\bunlocked\b", title):
                return "no", "carrier_specific"

        if item == "KitchenAid Artisan 5-Quart Stand Mixer":
            if not re.search(r"\b5[\s-]*(?:quart|qt)\b", title):
                return "review", "size_uncertain"

            # Reject bundles with additional equipment.
            if re.search(r"\bfood grinder\b", title):
                return "no", "enhanced_bundle"

    if item == 'Milwaukee M18 Fuel 1/2" Impact Wrench':
        # Require the correct model.
        if not re.search(r"\b2767-20\b", title):
            return "no", "model_mismatch"

        # Verify drive size.
        if not re.search(r"(?<!\d)1/2(?!\d)|\bhalf.inch\b", title):
            return "review", "drive_size_uncertain"

        if not re.search(r"\bimpact(?:\s+wrench)?\b", title):
            return "review", "tool_type_uncertain"

        # Flag uncertain condition.
        if re.search(r"\bread\b", title):
            return "review", "condition_uncertain"

    if item == "LEGO Star Wars Millennium Falcon 75257":
        # Reject clearly incomplete sets or component-only listings.
        if re.search(
            r"\bmissing\s+\d+\s+characters?\b|"
            r"\bpartial\s+build\b|"
            r"\bminifigures?\b.*\blot\b|"
            r"\bbags\s+only\b|"
            r"\bbuild\s+only\b",
            title
        ):
            return "no", "incomplete_product"

        # Review listings without explicit completeness confirmation.
        if not re.search(r"\bcomplete\b", title):
            return "review", "completeness_uncertain"

    if item == "Xbox Series X 1TB":
        if re.search(r"\b(digital|all-digital)\b", title):
            return "no", "digital_edition"

        if re.search(
            r"\b(\d+\s*(?:sealed\s*)?games?|"
            r"\d+\s*controllers?|pro controller)\b",
            title
        ):
            return "review", "bundle_or_accessories"

        if item == "Xbox Series X 1TB":
            if re.search(r"\bwhite\b", title):
                return "no", "wrong_edition"

        if re.search(r"\bwhite\b", title):
            return "review", "edition_uncertain"

    if item == "Sony PlayStation 5 Disc Edition":
    # Exclude the Slim model.
        if re.search(r"\bslim\b|\bcfi-20\d{2}\b", title):
            return "no", "wrong_model"

        # Review listings with unusual storage configurations.
        if re.search(r"\b1\s*tb\b", title):
            return "review", "storage_uncertain"

        # Review special editions.
        if re.search(r"\bspider.man\b|\bspecial edition\b", title):
            return "review", "special_edition"

        # Review bundles with extra games or controllers.
        if re.search(
            r"\b(\d+\s*(?:dualsense\s+)?controllers?|"
            r"games?|gta\s*5|god of war|last of us|accessories)\b",
            title
        ):
            return "review", "bundle_or_accessories"

        # Review console-only listings.
        if re.search(r"\bconsole only\b|\bsystem only\b", title):
            return "no", "incomplete_product"

        if item == "Sony PlayStation 5 Disc Edition":
            if re.search(r"\blow firmware\b|\bfirmware\b|\b\d{2}\.\d{2}\s*fw\b", title):
                return "no", "firmware_premium"

    # Exclude special-edition Nintendo consoles.
    if item == "Nintendo Switch OLED":
        if re.search(
            r"scarlet\s*(?:&|and|\+)?\s*violet|"
            r"super\s*mario\s*edition|"
            r"special\s*editions?",
            title,
            re.IGNORECASE
        ):
            return "no", "special_edition"

    # Exclude incomplete Switch Lite consoles.
    if item == "Nintendo Switch Lite":
        if re.search(
            r"display\s+w/o\s+joysticks|"
            r"screen\s+only|"
            r"replacement\s+display",
            title,
            re.IGNORECASE
        ):
            return "no", "incomplete_product"

    # Exclude multi-camera GoPro bundles.
    if item == "GoPro HERO11 Black":
        if re.search(r"\b[2-9]\s*x?\s*gopro\b", title, re.IGNORECASE):
            return "no", "multiple_units"

    # Dell XPS 13 9310 validation.
    if item == "Dell XPS 13 9310":

        # Exclude replacement components first.
        if re.search(
            r"screen\s+assembly|"
            r"display\s+assembly|"
            r"replacement\s+screen",
            title,
            re.IGNORECASE
        ):
            return "no", "replacement_part"

        if re.search(r"\bbase\s+only\b", title):
            return "no", "incomplete_product"

        # Exclude 2-in-1 models.
        if re.search(r"\b2[\s-]*in[\s-]*1\b", title):
            return "no", "wrong_form_factor"

        # Reject explicitly different processors.
        if re.search(r"\bi[3579][\s-]*\d{4,5}[a-z0-9]*\b", title):
            if not re.search(r"\bi7[\s-]*1185g7\b", title):
                return "no", "different_processor"

        # Manually verified Dell configuration
        if (
            item == "Dell XPS 13 9310"
            and str(row["listing_id"]) == "v1|327421547670|0"
        ):
            return "yes", "manually_verified"

        # Require 16GB RAM.
        if re.search(r"\b(?:8|32)\s*gb\b", title):
            return "no", "different_ram_configuration"

        # Require 512GB storage.
        if re.search(r"\b(?:256|954)\s*gb\b|\b(?:1|2)\s*tb\b", title):
            return "no", "different_storage_configuration"

        # Exclude higher-resolution displays.
        if re.search(r"\buhd\+?\b|\boled\b|\b3\.5k\b|\b4k\b", title):
            return "no", "different_display_configuration"

        # Missing specifications require manual review.
        if not all([
            re.search(r"\bi7-1185g7\b", title),
            re.search(r"\b16\s*gb\b", title),
            re.search(r"\b512\s*gb\b", title),
            re.search(r"\bfhd\+?\b", title),
        ]):
            return "review", "configuration_uncertain"

        if re.search(r"\bread\b", title):
            return "review", "condition_uncertain"

    return "yes", "valid_comparable"

def classify_configuration(row):
    if row["item_name"] != 'Milwaukee M18 Fuel 1/2" Impact Wrench':
        return "standard"

    # Manually verified tool-only listings
    verified_tool_only = {
        "v1|398448778116|0",
        "v1|287671828744|0",
    }

    listing_id = str(row["listing_id"])

    if listing_id in verified_tool_only:
        return "tool_only"

    title = str(row["listing_title"]).lower()

    if re.search(r"\b(battery|batteries|batt|charger|kit|combo)\b", title):
        return "kit"

    if re.search(r"\b(tool.only|bare.tool|bare|without.battery)\b", title):
        return "tool_only"

    return "unclear"

def main():
    df = pd.read_csv(CANDIDATES)
    df["configuration"] = df.apply(classify_configuration, axis=1)

    df[["include", "reason"]] = df.apply(
        lambda row: pd.Series(classify_listing(row)),
        axis=1
    )

    # Duplicate listing IDs within the same product are counted once.
    duplicate = (
        df["listing_id"].notna()
        & df.duplicated(["item_name", "listing_id"], keep="first")
    )
    df.loc[duplicate, ["include", "reason"]] = [
        "no", "duplicate_listing_id"
    ]

    # Manually verified listings exempt from outlier filtering
    verified_outlier_exceptions = {
        "v1|257206762018|0",   # Milwaukee tool only
         "v1|336686959744|0",  # Dell XPS 13 9310
    }

    # Flag price outliers within each product's accepted listings.
    for (item, configuration), group in df[
        df["include"] == "yes"
    ].groupby(["item_name", "configuration"]):
        if len(group) < 5:
            continue

        prices = pd.to_numeric(group["listing_price"], errors="coerce")

        q1 = prices.quantile(0.25)
        q3 = prices.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outliers = group.index[
            ((prices < lower) | (prices > upper))
            & ~group["listing_id"].astype(str).isin(verified_outlier_exceptions)
        ]

        df.loc[outliers, "include"] = "review"
        df.loc[outliers, "reason"] = "price_outlier"

    summary = (
        df.groupby(["item_name", "include"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["yes", "no", "review"], fill_value=0)
    )

    summary["status"] = summary["yes"].apply(
        lambda count: "insufficient_data" if count < 5 else "ready_for_review"
    )

    print(summary.to_string())
    print("\nTotal decisions:")
    print(df["include"].value_counts().to_string())

    # Calculate provisional reference values from accepted listings.
    accepted = df[
        (df["include"] == "yes")
        & (df["item_name"] != 'Milwaukee M18 Fuel 1/2" Impact Wrench')
    ].copy()

    accepted["listing_price"] = pd.to_numeric(
        accepted["listing_price"], errors="coerce"
    )

    medians = (
        accepted.groupby("item_name")["listing_price"]
        .agg(["count", "median"])
        .round(2)
    )

    milwaukee = df[
        (df["item_name"] == 'Milwaukee M18 Fuel 1/2" Impact Wrench')
        & (df["include"] == "yes")
        & (df["configuration"].isin(["kit", "tool_only"]))
    ]

    configuration_values = (
        milwaukee.groupby("configuration")["listing_price"]
        .agg(["count", "median"])
    )

    configuration_values["status"] = configuration_values["count"].apply(
        lambda count: "provisional" if count >= 5 else "insufficient_data"
    )

    configuration_values.loc[
        configuration_values["count"] < 5, "median"
    ] = float("nan")

    print("\nMilwaukee reference values by configuration:")
    print(configuration_values)

    medians["status"] = medians["count"].apply(
        lambda n: "insufficient_data" if n < 5 else "provisional"
    )

    medians.loc[
        medians["status"] == "insufficient_data", "median"
    ] = float("nan")

    print("\nProvisional reference values:")
    print(medians.to_string())

    # Export provisional reference values
    standard_export = medians.reset_index().copy()
    standard_export["configuration"] = "standard"

    milwaukee_export = configuration_values.reset_index().copy()
    milwaukee_export["item_name"] = 'Milwaukee M18 Fuel 1/2" Impact Wrench'

    reference_values = pd.concat(
        [standard_export, milwaukee_export],
        ignore_index=True
    )

    reference_values = reference_values[
        ["item_name", "configuration", "count", "median", "status"]
    ]

    output_path = CANDIDATES.parent / "ground_truth_reference_values.csv"

    reference_values.to_csv(output_path, index=False)

    print(f"\nSaved reference values: {output_path}")

    # Preview only. Never overwrite original CSV files.
    preview = DATA_DIR / "ground_truth_candidates_expanded_preview.csv"
    df.to_csv(preview, index=False)
    print(f"\nSaved preview: {preview}")


if __name__ == "__main__":
    main()
