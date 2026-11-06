import csv
from io import StringIO

from ..utilities.constants import CSV_COLUMN_HEADERS


def build_csv_report(
    items,
    *,
    include_purchase_prices,
    include_current_values,
    include_serial_numbers,
):
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)

    headers = list(CSV_COLUMN_HEADERS)
    if include_serial_numbers:
        headers.extend(["Model Number", "Serial Number"])
    if include_purchase_prices:
        headers.extend(["Purchase Date", "Purchase Price"])
    if include_current_values:
        headers.append("Current Value")
    writer.writerow(headers)

    for item in items:
        row = [
            item.name,
            item.category.name if item.category else "Uncategorized",
            item.location.name if item.location else "",
            item.description,
            item.brand,
            item.get_condition_display(),
            item.quantity,
        ]

        if include_serial_numbers:
            row.extend([item.model_number, item.serial_number])
        if include_purchase_prices:
            row.extend(
                [
                    item.purchase_date.isoformat() if item.purchase_date else "",
                    item.purchase_amount if item.purchase_amount is not None else "",
                ]
            )
        if include_current_values:
            row.append(item.effective_value if item.effective_value is not None else "")
        writer.writerow(row)

    return output.getvalue()
