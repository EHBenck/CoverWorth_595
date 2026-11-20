"""Build repeatable, clearly labeled sample data for local CoverWorth demos.

Usage: python backend/manage.py seed_demo [--reset]
The command never contacts eBay or writes to another user's inventories.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import os
import secrets
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection, transaction

from myapp.models import (
    Category,
    Inventory,
    InventoryType,
    Item,
    ItemCondition,
    Location,
    ValuationRun,
    ValuationStatus,
    ValuationType,
)

DEMO_USERNAME = "coverworth_demo"
DEMO_EMAIL = "demo@coverworth.example"

# Static fixture values are intentionally not claimed to be live appraisals.
# Stable IDs make repeated seed runs update, rather than duplicate, sample rows.
DEMO_INVENTORIES = (
    {
        "slug": "home",
        "name": "Demo - Home & Personal",
        "description": "Sample home belongings for a CoverWorth walkthrough.",
        "inventory_type": InventoryType.HOME,
        "categories": ("Electronics", "Furniture", "Appliances", "Outdoor Gear"),
        # (key, display name, parent key): parent always appears first.
        "locations": (
            ("home", "Home", None),
            ("office", "Office", "home"),
            ("desk", "Desk", "office"),
            ("living", "Living Room", "home"),
            ("kitchen", "Kitchen", "home"),
            ("garage", "Garage", "home"),
        ),
        "items": (
            {
                "key": "laptop", "name": "Dell XPS 13 Laptop",
                "category": "Electronics", "location": "office",
                "brand": "Dell", "condition": ItemCondition.USED,
                "purchase_date": date(2024, 8, 15), "purchase_amount": "1299.00",
                "manual_value": "850.00",
                "description": "13-inch work laptop, charger included.",
            },
            {
                "key": "headphones", "name": "Sony WH-1000XM5 Headphones",
                "category": "Electronics", "location": "desk",
                "brand": "Sony", "condition": ItemCondition.LIKE_NEW,
                "purchase_date": date(2025, 2, 6), "purchase_amount": "349.99",
                "manual_value": "220.00",
                "description": "Noise-canceling headphones with carrying case.",
            },
            {
                "key": "iphone13", "name": "Apple iPhone 13 128GB",
                "category": "Electronics", "location": "desk",
                "brand": "Apple", "model_number": "iPhone 13 128GB",
                "condition": ItemCondition.USED,
                "purchase_date": date(2022, 4, 10), "purchase_amount": "799.00",
                "description": "Example device for the limited iPhone 13 valuation prototype.",
            },
            {
                "key": "tv", "name": "LG 55-inch OLED TV",
                "category": "Electronics", "location": "living",
                "brand": "LG", "condition": ItemCondition.USED,
                "purchase_date": date(2023, 11, 27), "purchase_amount": "1199.99",
            },
            {
                "key": "desk", "name": "Walnut Writing Desk",
                "category": "Furniture", "location": "office",
                "condition": ItemCondition.USED,
                "purchase_date": date(2020, 6, 12), "purchase_amount": "540.00",
                "manual_value": "400.00",
            },
            {
                "key": "mixer", "name": "KitchenAid Stand Mixer",
                "category": "Appliances", "location": "kitchen",
                "brand": "KitchenAid", "condition": ItemCondition.USED,
                "purchase_date": date(2024, 3, 4), "purchase_amount": "379.99",
            },
            {
                "key": "tent", "name": "Two-Person Camping Tent",
                "category": "Outdoor Gear", "location": "garage",
                "condition": ItemCondition.USED, "quantity": 1,
                "purchase_date": date(2024, 5, 18), "purchase_amount": "185.00",
            },
        ),
    },
    {
        "slug": "collection",
        "name": "Demo - Collectibles",
        "description": "Sample collection with different categories and nested locations.",
        "inventory_type": InventoryType.COLLECTION,
        "categories": ("Video Games", "Photography", "Music"),
        "locations": (
            ("storage", "Collection Storage", None),
            ("shelf", "Display Shelf", "storage"),
            ("cabinet", "Camera Cabinet", "storage"),
        ),
        "items": (
            {
                "key": "switch", "name": "Nintendo Switch OLED",
                "category": "Video Games", "location": "shelf",
                "brand": "Nintendo", "condition": ItemCondition.USED,
                "purchase_date": date(2022, 10, 11), "purchase_amount": "349.99",
                "manual_value": "210.00",
            },
            {
                "key": "camera", "name": "Fujifilm X-T4 Camera",
                "category": "Photography", "location": "cabinet",
                "brand": "Fujifilm", "condition": ItemCondition.LIKE_NEW,
                "purchase_date": date(2023, 7, 1), "purchase_amount": "1299.00",
                "manual_value": "925.00",
            },
            {
                "key": "records", "name": "Vinyl Record Collection",
                "category": "Music", "location": "shelf",
                "condition": ItemCondition.USED, "quantity": 12,
                "purchase_date": date(2024, 1, 15), "purchase_amount": "300.00",
                "description": "Twelve assorted records tracked as one item.",
            },
        ),
    },
)


def demo_id(*parts):
    """Generate a stable, namespaced public UUID for a demo-only record."""
    return uuid5(NAMESPACE_URL, "coverworth-595/demo/v1/" + "/".join(parts))


def upsert_scoped(model, public_id, relation_name, parent, values):
    """Create/update a demo record without transferring another owner's data."""
    data = {relation_name: parent, **values}
    obj, created = model.objects.get_or_create(public_id=public_id, defaults=data)
    if not created:
        if getattr(obj, f"{relation_name}_id") != parent.pk:
            raise CommandError(
                f"Refusing to repurpose {model.__name__} {public_id}: "
                f"it belongs to a different {relation_name}."
            )
        changed = []
        for field, value in values.items():
            if getattr(obj, field) != value:
                setattr(obj, field, value)
                changed.append(field)
        if changed:
            if hasattr(obj, "updated_at"):
                changed.append("updated_at")
            obj.full_clean()
            obj.save(update_fields=changed)
    return obj


class Command(BaseCommand):
    help = "Seed or restore reproducible sample inventories, items, and valuations for local demos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete and recreate ONLY the two named demo inventories (including their contents).",
        )
        parser.add_argument(
            "--allow-remote-db", action="store_true",
            help="Explicitly allow a development PostgreSQL database; never allowed with DEBUG=False.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding requires DEBUG=True; refusing to modify production data.")
        if connection.vendor != "sqlite" and not options["allow_remote_db"]:
            raise CommandError(
                "Demo seeding defaults to local SQLite. For an isolated development "
                "PostgreSQL database, explicitly pass --allow-remote-db."
            )

        password = os.environ.get("COVERWORTH_DEMO_PASSWORD", "").strip()
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError("COVERWORTH_DEMO_PASSWORD: " + " ".join(exc.messages)) from exc

        try:
            with transaction.atomic():
                User = get_user_model()
                user = User.objects.filter(username=DEMO_USERNAME).first()
                if user is not None:
                    if user.email != DEMO_EMAIL or user.is_staff or user.is_superuser:
                        raise CommandError(
                            "The demo username belongs to a different or privileged account. "
                            "Refusing to modify it."
                        )
                    created_user = False
                else:
                    if User.objects.filter(email__iexact=DEMO_EMAIL).exists():
                        raise CommandError("The demo email belongs to another account.")
                    user = User(username=DEMO_USERNAME, email=DEMO_EMAIL, first_name="CoverWorth", last_name="Demo")
                    created_user = True

                # Generate only for a newly created user; never rotate a password
                # on a rerun unless the developer explicitly supplied one.
                generated_password = None
                if created_user or (password and not user.check_password(password)):
                    if not password:
                        generated_password = secrets.token_urlsafe(24)
                        password = generated_password
                    user.set_password(password)
                    user.save()

                if options["reset"]:
                    ids = [demo_id("inventory", spec["slug"]) for spec in DEMO_INVENTORIES]
                    Inventory.objects.filter(owner=user, public_id__in=ids).delete()

                for spec in DEMO_INVENTORIES:
                    slug = spec["slug"]
                    inventory = upsert_scoped(
                        Inventory, demo_id("inventory", slug), "owner", user,
                        {
                            "name": spec["name"],
                            "description": spec["description"],
                            "inventory_type": spec["inventory_type"],
                            "default_currency": "USD",
                            "archived_at": None,
                        },
                    )
                    categories = {
                        name: upsert_scoped(
                            Category, demo_id("category", slug, name), "inventory", inventory,
                            {"name": name, "description": "Sample category", "archived_at": None},
                        )
                        for name in spec["categories"]
                    }
                    locations = {}
                    for key, name, parent_key in spec["locations"]:
                        locations[key] = upsert_scoped(
                            Location, demo_id("location", slug, key), "inventory", inventory,
                            {"name": name, "parent": locations.get(parent_key), "archived_at": None},
                        )
                    for item_data in spec["items"]:
                        values = {
                            "name": item_data["name"],
                            "category": categories[item_data["category"]],
                            "location": locations[item_data["location"]],
                            "description": item_data.get("description", ""),
                            "brand": item_data.get("brand", ""),
                            "model_number": item_data.get("model_number", ""),
                            "condition": item_data.get("condition", ItemCondition.UNKNOWN),
                            "quantity": item_data.get("quantity", 1),
                            "purchase_date": item_data.get("purchase_date"),
                            "purchase_amount": Decimal(item_data["purchase_amount"]),
                            "manual_value": (
                                Decimal(item_data["manual_value"])
                                if "manual_value" in item_data else None
                            ),
                            "current_estimated_amount": None,
                            "archived_at": None,
                            "is_archived": False,
                        }
                        item = upsert_scoped(
                            Item, demo_id("item", slug, item_data["key"]),
                            "inventory", inventory, values,
                        )
                        if values["manual_value"] is not None:
                            upsert_scoped(
                                ValuationRun,
                                demo_id("valuation", slug, item_data["key"]),
                                "item", item,
                                {
                                    "requested_by": user,
                                    "valuation_type": ValuationType.MANUAL,
                                    "status": ValuationStatus.SUCCESS,
                                    "estimated_amount": values["manual_value"],
                                    "currency": "USD",
                                    "algorithm_version": "demo-seed-v1",
                                    "input_snapshot": {
                                        "demo_fixture": True,
                                        "note": "Sample manual value; not a live eBay estimate.",
                                    },
                                    "started_at": datetime(2026, 1, 15, tzinfo=timezone.utc),
                                    "completed_at": datetime(2026, 1, 15, tzinfo=timezone.utc),
                                },
                            )
        except (IntegrityError, ValidationError) as exc:
            raise CommandError(
                "Cannot seed demo records due to an existing data conflict: " + str(exc)
            ) from exc

        counts = {
            "inventories": Inventory.objects.filter(owner=user, public_id__in=[
                demo_id("inventory", spec["slug"]) for spec in DEMO_INVENTORIES
            ]).count(),
            "categories": sum(len(spec["categories"]) for spec in DEMO_INVENTORIES),
            "locations": sum(len(spec["locations"]) for spec in DEMO_INVENTORIES),
            "items": sum(len(spec["items"]) for spec in DEMO_INVENTORIES),
        }
        self.stdout.write(self.style.SUCCESS(
            "Demo data ready for username '" + DEMO_USERNAME + "': "
            + ", ".join(f"{count} {label}" for label, count in counts.items())
            + "."
        ))
        if generated_password:
            self.stdout.write("Generated demo password (shown once): " + generated_password)
        elif password:
            self.stdout.write("Demo login password is the configured COVERWORTH_DEMO_PASSWORD.")
        else:
            self.stdout.write("Existing demo password preserved; set COVERWORTH_DEMO_PASSWORD to change it.")
