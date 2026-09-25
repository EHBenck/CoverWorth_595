from decimal import Decimal, InvalidOperation

from django.http import JsonResponse

from myapp.models import Item


def dashboard_summary(request):
    items = Item.objects.select_related("category").filter(archived_at__isnull=True)

    total_items = items.count()
    total_value = 0.0
    category_totals = {}

    for item in items:
        value = item.manual_value

        if value is None:
            raw_value = item.current_estimated_amount
            try:
                value = Decimal(str(raw_value or 0))
            except (InvalidOperation, TypeError, ValueError):
                value = Decimal("0")

        if isinstance(value, Decimal):
            numeric_value = float(value)
        else:
            try:
                numeric_value = float(value or 0)
            except (TypeError, ValueError):
                numeric_value = 0.0

        total_value += numeric_value

        category_name = item.category.name if item.category else "Uncategorized"
        category_totals[category_name] = category_totals.get(category_name, 0.0) + numeric_value

    payload = {
        "total_items": total_items,
        "total_value": round(total_value, 2),
        "categories": {key: round(value, 2) for key, value in sorted(category_totals.items())},
    }

    return JsonResponse(payload)
