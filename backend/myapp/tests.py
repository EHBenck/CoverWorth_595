from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import (
    Category,
    Inventory,
    Item,
    Location,
)


User = get_user_model()


class CoverWorthBackendTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.inventory = Inventory.objects.create(
            owner=self.user,
            name="Test Inventory",
            default_currency="USD",
        )

        self.category = Category.objects.create(
            inventory=self.inventory,
            name="Electronics",
        )

        self.location = Location.objects.create(
            inventory=self.inventory,
            name="Office",
        )

        self.item = Item.objects.create(
            inventory=self.inventory,
            category=self.category,
            location=self.location,
            name="Test Laptop",
            condition="used",
            quantity=1,
            purchase_amount_minor=125000,
            current_estimated_amount_minor=95000,
        )


    def test_database_models_created(self):
        """Make sure our models can read/write to the database."""

        self.assertEqual(
            Inventory.objects.count(),
            1,
        )

        self.assertEqual(
            Category.objects.count(),
            1,
        )

        self.assertEqual(
            Location.objects.count(),
            1,
        )

        self.assertEqual(
            Item.objects.count(),
            1,
        )

        item = Item.objects.get(
            name="Test Laptop"
        )

        self.assertEqual(
            item.inventory.name,
            "Test Inventory",
        )

        self.assertEqual(
            item.category.name,
            "Electronics",
        )

        self.assertEqual(
            item.location.name,
            "Office",
        )


    def test_health_endpoint(self):
        """Make sure Django can reach the CoverWorth database."""

        response = self.client.get(
            reverse("health-check")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["status"],
            "ok",
        )

        self.assertEqual(
            data["database"],
            "connected",
        )

        self.assertEqual(
            data["item_rows"],
            1,
        )


    def test_items_endpoint(self):
        """Make sure the API returns database items."""

        response = self.client.get(
            reverse("item-list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertIn(
            "items",
            data,
        )

        self.assertEqual(
            len(data["items"]),
            1,
        )

        item = data["items"][0]

        self.assertEqual(
            item["name"],
            "Test Laptop",
        )

        self.assertEqual(
            item["inventory"],
            "Test Inventory",
        )

        self.assertEqual(
            item["category"],
            "Electronics",
        )

        self.assertEqual(
            item["location"],
            "Office",
        )

        self.assertEqual(
            item["quantity"],
            1,
        )

        self.assertEqual(
            item["purchase_value"],
            1250.00,
        )

        self.assertEqual(
            item["estimated_value"],
            950.00,
        )


    def test_dashboard_endpoint(self):
        """Make sure dashboard calculations use database values."""

        response = self.client.get(
            reverse("dashboard-summary")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        summary = data["summary"]

        self.assertEqual(
            summary["total_items"],
            1,
        )

        self.assertEqual(
            summary["purchase_value"],
            1250.00,
        )

        self.assertEqual(
            summary["estimated_value"],
            950.00,
        )

        # valuation_date is empty, so this item
        # should require attention.
        self.assertEqual(
            summary["items_needing_attention"],
            1,
        )

        self.assertEqual(
            data["category_data"][0]["name"],
            "Electronics",
        )

        self.assertEqual(
            data["category_data"][0]["value"],
            950.00,
        )

        self.assertEqual(
            data["recent_items"][0]["name"],
            "Test Laptop",
        )


    def test_item_cannot_use_category_from_other_inventory(self):
        """
        Verify that an item cannot accidentally use a category
        belonging to someone else's inventory.
        """

        other_inventory = Inventory.objects.create(
            owner=self.user,
            name="Other Inventory",
        )

        other_category = Category.objects.create(
            inventory=other_inventory,
            name="Furniture",
        )

        self.item.category = other_category

        with self.assertRaises(ValidationError):
            self.item.full_clean()