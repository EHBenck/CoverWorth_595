from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Item


VALUATION_STALE_AFTER_DAYS = 90


def _money_from_minor(amount_minor):
    if amount_minor is None:
        return 0.0

    return round(amount_minor / 100, 2)


def _effective_value_minor(item):
    if item.manual_value_minor is not None:
        return item.manual_value_minor

    return item.current_estimated_amount_minor or 0


@require_GET
def dashboard_summary(request):
    """Return database-backed data for the NiceGUI dashboard."""

    items = list(
        Item.objects.filter(
            archived_at__isnull=True
        )
        .select_related(
            "category",
            "inventory",
        )
        .order_by("-updated_at")
    )

    purchase_total_minor = sum(
        item.purchase_amount_minor or 0
        for item in items
    )

    estimate_total_minor = sum(
        _effective_value_minor(item)
        for item in items
    )

    category_totals = {}

    for item in items:
        category_name = (
            item.category.name
            if item.category
            else "Uncategorized"
        )

        category_totals[category_name] = (
            category_totals.get(category_name, 0)
            + _effective_value_minor(item)
        )

    stale_before = (
        timezone.now()
        - timedelta(days=VALUATION_STALE_AFTER_DAYS)
    )

    needs_attention = sum(
        1
        for item in items
        if item.valuation_date is None
        or item.valuation_date < stale_before
    )

    recent_items = []

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
                "value": _money_from_minor(
                    _effective_value_minor(item)
                ),
                "date": (
                    item.updated_at
                    .strftime("%b %d, %Y")
                    .replace(" 0", " ")
                ),
            }
        )

    category_data = [
        {
            "name": name,
            "value": _money_from_minor(value_minor),
        }
        for name, value_minor in sorted(
            category_totals.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )
    ]

    return JsonResponse(
        {
            "summary": {
                "total_items": len(items),
                "estimated_value": _money_from_minor(
                    estimate_total_minor
                ),
                "purchase_value": _money_from_minor(
                    purchase_total_minor
                ),
                "items_needing_attention": needs_attention,
            },
            "category_data": category_data,
            "recent_items": recent_items,
        }
    )


@require_GET
def item_list(request):
    """Read-only item endpoint."""

    items = (
        Item.objects.filter(
            archived_at__isnull=True
        )
        .select_related(
            "category",
            "location",
            "inventory",
        )
        .order_by("-updated_at")[:100]
    )

    return JsonResponse(
        {
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
                    "purchase_value": _money_from_minor(
                        item.purchase_amount_minor
                    ),
                    "estimated_value": _money_from_minor(
                        _effective_value_minor(item)
                    ),
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in items
            ]
        }
    )