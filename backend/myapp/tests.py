import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from myapp.models import (
    Category,
    Inventory,
    Item,
    ValuationRun,
    ValuationSourceResult,
)

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
        self.client.force_login(self.user)

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

    def test_dashboard_and_items_require_authentication(self):
        self.client.logout()

        dashboard_response = self.client.get("/api/dashboard/")
        items_response = self.client.get("/api/items/")

        self.assertEqual(dashboard_response.status_code, 401)
        self.assertEqual(items_response.status_code, 401)

    def test_inventory_and_item_endpoints_require_authentication(self):
        item = Item.objects.first()
        self.client.logout()

        paths = [
            f"/api/inventory/{self.inventory.public_id}/",
            f"/api/inventory/{self.inventory.public_id}/add-item/",
            f"/api/item/{item.public_id}/",
            f"/api/item/{item.public_id}/edit/",
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_dashboard_only_returns_authenticated_users_inventory(self):
        another_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="another-secret",
        )
        another_inventory = Inventory.objects.create(
            owner=another_user,
            name="Bob inventory",
        )
        Item.objects.create(
            inventory=another_inventory,
            name="Bob's item",
            manual_value=Decimal("9999.00"),
        )

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["total_items"], 3)
        self.assertEqual(
            response.json()["summary"]["estimated_value"],
            2100.0,
        )


class AuthenticationAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            password="correct-secret",
        )

    def test_login_accepts_valid_credentials(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "alice", "password": "correct-secret"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertTrue(self.client.get("/api/dashboard/").wsgi_request.user.is_authenticated)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "alice", "password": "wrong-secret"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_logout_clears_the_authenticated_session(self):
        self.client.force_login(self.user)

        response = self.client.post("/api/auth/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 401)

    def test_login_requires_post(self):
        response = self.client.get("/api/auth/login/")

        self.assertEqual(response.status_code, 405)

class ItemDeletionAPITestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="delete-user",
            password="secret",
        )

        self.client.force_login(self.user)

        self.inventory = Inventory.objects.create(
            owner=self.user,
            name="Delete test inventory",
        )

        self.item = Item.objects.create(
            inventory=self.inventory,
            name="Camera",
            purchase_amount=Decimal("900.00"),
            manual_value=Decimal("700.00"),
        )


    def test_archive_soft_deletes_item(self):
        response = self.client.post(
            f"/api/item/{self.item.public_id}/archive/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.item.refresh_from_db()

        # Soft delete means the row remains.
        self.assertIsNotNone(
            self.item.archived_at
        )

        self.assertTrue(
            Item.objects.filter(
                pk=self.item.pk
            ).exists()
        )

        # But it disappears from Inventory.
        items_response = self.client.get(
            "/api/items/"
        )

        self.assertEqual(
            items_response.json()["items"],
            [],
        )

        # And disappears from Dashboard totals.
        dashboard_response = self.client.get(
            "/api/dashboard/"
        )

        self.assertEqual(
            dashboard_response.json()
            ["summary"]
            ["total_items"],
            0,
        )

        self.assertEqual(
            dashboard_response.json()
            ["summary"]
            ["estimated_value"],
            0,
        )


    def test_archiving_an_already_archived_item_returns_404(self):

        first_response = self.client.post(
            f"/api/item/{self.item.public_id}/archive/"
        )

        second_response = self.client.post(
            f"/api/item/{self.item.public_id}/archive/"
        )

        self.assertEqual(
            first_response.status_code,
            200,
        )

        self.assertEqual(
            second_response.status_code,
            404,
        )


    def test_permanent_delete_removes_item_and_related_rows(self):

        valuation = ValuationRun.objects.create(
            item=self.item,
            requested_by=self.user,
        )

        source_result = ValuationSourceResult.objects.create(
            valuation_run=valuation,
            source="test-source",
        )

        item_pk = self.item.pk
        valuation_pk = valuation.pk
        source_result_pk = source_result.pk

        response = self.client.delete(
            f"/api/item/{self.item.public_id}/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Actual Item record is gone.
        self.assertFalse(
            Item.objects.filter(
                pk=item_pk
            ).exists()
        )

        # ValuationRun CASCADE worked.
        self.assertFalse(
            ValuationRun.objects.filter(
                pk=valuation_pk
            ).exists()
        )

        # ValuationSourceResult CASCADE worked.
        self.assertFalse(
            ValuationSourceResult.objects.filter(
                pk=source_result_pk
            ).exists()
        )


    def test_permanent_delete_can_remove_archived_item(self):

        archive_response = self.client.post(
            f"/api/item/{self.item.public_id}/archive/"
        )

        self.assertEqual(
            archive_response.status_code,
            200,
        )

        delete_response = self.client.delete(
            f"/api/item/{self.item.public_id}/"
        )

        self.assertEqual(
            delete_response.status_code,
            200,
        )

        self.assertFalse(
            Item.objects.filter(
                pk=self.item.pk
            ).exists()
        )


    def test_invalid_permanent_delete_returns_404(self):

        response = self.client.delete(
            f"/api/item/{uuid.uuid4()}/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )


    def test_user_cannot_archive_or_delete_another_users_item(self):

        other_user = User.objects.create_user(
            username="other-user",
            password="secret",
        )

        other_inventory = Inventory.objects.create(
            owner=other_user,
            name="Other inventory",
        )

        other_item = Item.objects.create(
            inventory=other_inventory,
            name="Other camera",
        )

        archive_response = self.client.post(
            f"/api/item/{other_item.public_id}/archive/"
        )

        delete_response = self.client.delete(
            f"/api/item/{other_item.public_id}/"
        )

        self.assertEqual(
            archive_response.status_code,
            403,
        )

        self.assertEqual(
            delete_response.status_code,
            403,
        )

        self.assertTrue(
            Item.objects.filter(
                pk=other_item.pk
            ).exists()
        )


    def test_archive_and_delete_require_authentication(self):

        self.client.logout()

        archive_response = self.client.post(
            f"/api/item/{self.item.public_id}/archive/"
        )

        delete_response = self.client.delete(
            f"/api/item/{self.item.public_id}/"
        )

        self.assertEqual(
            archive_response.status_code,
            401,
        )

        self.assertEqual(
            delete_response.status_code,
            401,
        )