from decimal import Decimal

from django.http import JsonResponse

from myapp.models import Item


def dashboard_summary(request):
    items = (
        Item.objects
        .select_related("category")
        .filter(archived_at__isnull=True)
        .order_by("-updated_at")
    )

    total_items = items.count()
    estimated_value = Decimal("0.00")
    purchase_value = Decimal("0.00")
    category_totals = {}

    recent_items = []

    for item in items:
        current_value = item.effective_value or Decimal("0.00")
        current_purchase = item.purchase_amount or Decimal("0.00")

        estimated_value += current_value
        purchase_value += current_purchase

        category_name = (
            item.category.name
            if item.category
            else "Uncategorized"
        )

        category_totals[category_name] = (
            category_totals.get(
                category_name,
                Decimal("0.00"),
            )
            + current_value
        )

    for item in items[:5]:
        recent_items.append(
            {
                "public_id": str(item.public_id),
                "name": item.name,
                "category": (
                    item.category.name
                    if item.category
                    else "Uncategorized"
                ),
                "value": float(
                    item.effective_value
                    or Decimal("0.00")
                ),
                "date": item.updated_at.strftime(
                    "%b %d, %Y"
                ).replace(" 0", " "),
                "icon": "inventory_2",
            }
        )

    category_data = [
        {
            "name": name,
            "value": float(value),
        }
        for name, value in sorted(
            category_totals.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )
    ]

    payload = {
        "summary": {
            "total_items": total_items,
            "estimated_value": float(estimated_value),
            "purchase_value": float(purchase_value),
            "items_needing_attention": items.filter(
                valuation_date__isnull=True
            ).count(),
        },
        "category_data": category_data,
        "recent_items": recent_items,
    }

    return JsonResponse(payload)


def item_list(request):
    items = (
        Item.objects
        .select_related(
            "inventory",
            "category",
            "location",
        )
        .filter(archived_at__isnull=True)
        .order_by("-updated_at")
    )

    payload = {
        "items": [
            {
                "public_id": str(item.public_id),
                "name": item.name,
                "inventory": item.inventory.name,
                "category": (
                    item.category.name
                    if item.category
                    else None
                ),
                "location": (
                    item.location.name
                    if item.location
                    else None
                ),
                "quantity": item.quantity,
                "condition": item.condition,
                "purchase_value": (
                    float(item.purchase_amount)
                    if item.purchase_amount is not None
                    else None
                ),
                "estimated_value": (
                    float(item.effective_value)
                    if item.effective_value is not None
                    else None
                ),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }

    return JsonResponse(payload)