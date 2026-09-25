from decimal import Decimal

from django.test import TestCase

from myapp.models import Category, Inventory, Item, User


class DashboardSummaryAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
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
            manual_value=1200,
            manual_value_currency="USD",
        )
        Item.objects.create(
            inventory=self.inventory,
            category=self.furniture,
            name="Chair",
            quantity=2,
            manual_value=300,
            manual_value_currency="USD",
        )
        Item.objects.create(
            inventory=self.inventory,
            category=self.electronics,
            name="Phone",
            quantity=1,
            manual_value=600,
            manual_value_currency="USD",
        )

    def test_dashboard_summary_returns_expected_shape(self):
        response = self.client.get("/api/dashboard-summary/")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total_items"], 3)
        self.assertEqual(Decimal(str(data["total_value"])), Decimal("2100"))
        self.assertEqual(data["categories"]["Electronics"], 1800.0)
        self.assertEqual(data["categories"]["Furniture"], 300.0)

    def test_dashboard_summary_handles_empty_database(self):
        Item.objects.all().delete()
        Category.objects.all().delete()
        Inventory.objects.all().delete()
        User.objects.all().delete()

        response = self.client.get("/api/dashboard-summary/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_items"], 0)
        self.assertEqual(data["total_value"], 0)
        self.assertEqual(data["categories"], {})
