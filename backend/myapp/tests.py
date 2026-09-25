from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from myapp.models import Category, Inventory, Item


User = get_user_model()


class DashboardSummaryAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="secret",
            first_name="Alice",
            last_name="Smith",
        )

        self.inventory = Inventory.objects.create(
            owner=self.user,
            name="Main inventory",
            description="Test inventory",
            default_currency="USD",
            inventory_type="personal",
        )

        self.electronics = Category.objects.create(
            inventory=self.inventory,
            name="Electronics",
        )

        self.furniture = Category.objects.create(
            inventory=self.inventory,
            name="Furniture",
        )

        Item.objects.create(
            inventory=self.inventory,
            category=self.electronics,
            name="Laptop",
            quantity=1,
            purchase_amount=Decimal("1400.00"),
            current_estimated_amount=Decimal("1100.00"),
            manual_value=Decimal("1200.00"),
        )

        Item.objects.create(
            inventory=self.inventory,
            category=self.furniture,
            name="Chair",
            quantity=2,
            purchase_amount=Decimal("250.00"),
            current_estimated_amount=Decimal("300.00"),
            manual_value=Decimal("300.00"),
        )

        Item.objects.create(
            inventory=self.inventory,
            category=self.electronics,
            name="Phone",
            quantity=1,
            purchase_amount=Decimal("700.00"),
            current_estimated_amount=Decimal("600.00"),
            manual_value=Decimal("600.00"),
        )


    def test_dashboard_summary_returns_expected_shape(self):
        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        summary = data["summary"]

        self.assertEqual(
            summary["total_items"],
            3,
        )

        self.assertEqual(
            Decimal(str(summary["estimated_value"])),
            Decimal("2100.00"),
        )

        self.assertEqual(
            Decimal(str(summary["purchase_value"])),
            Decimal("2350.00"),
        )

        category_values = {
            category["name"]: category["value"]
            for category in data["category_data"]
        }

        self.assertEqual(
            category_values["Electronics"],
            1800.0,
        )

        self.assertEqual(
            category_values["Furniture"],
            300.0,
        )

        self.assertEqual(
            len(data["recent_items"]),
            3,
        )


    def test_dashboard_summary_handles_empty_database(self):
        Item.objects.all().delete()

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            data["summary"]["total_items"],
            0,
        )

        self.assertEqual(
            data["summary"]["estimated_value"],
            0,
        )

        self.assertEqual(
            data["summary"]["purchase_value"],
            0,
        )

        self.assertEqual(
            data["category_data"],
            [],
        )

        self.assertEqual(
            data["recent_items"],
            [],
        )


    def test_manual_value_overrides_estimated_value(self):
        laptop = Item.objects.get(name="Laptop")

        laptop.manual_value = Decimal("1300.00")
        laptop.save()

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            Decimal(
                str(
                    data["summary"]["estimated_value"]
                )
            ),
            Decimal("2200.00"),
        )


    def test_items_endpoint(self):
        response = self.client.get("/api/items/")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            len(data["items"]),
            3,
        )

        laptop = next(
            item
            for item in data["items"]
            if item["name"] == "Laptop"
        )

        self.assertEqual(
            laptop["category"],
            "Electronics",
        )

        self.assertEqual(
            laptop["purchase_value"],
            1400.0,
        )

        self.assertEqual(
            laptop["estimated_value"],
            1200.0,
        )