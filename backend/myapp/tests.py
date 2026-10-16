from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from myapp.test_integration import FrontendClient, PASSWORD
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


class RegistrationAPITestCase(TestCase):
    def setUp(self):
        self.payload = {
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@example.com",
            "username": "bob",
            "password": "Sturdy-passphrase-42",
            "password_confirm": "Sturdy-passphrase-42",
        }

    def register(self, **overrides):
        return self.client.post(
            "/api/auth/register/",
            data={**self.payload, **overrides},
            content_type="application/json",
        )

    def test_register_creates_user_inventory_and_session(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["username"], "bob")

        user = User.objects.get(username="bob")
        self.assertEqual(user.first_name, "Bob")
        self.assertEqual(user.last_name, "Smith")
        self.assertEqual(user.email, "bob@example.com")
        self.assertTrue(user.check_password("Sturdy-passphrase-42"))
        self.assertTrue(Inventory.objects.filter(owner=user).exists())

        dashboard = self.client.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIsNotNone(dashboard.json()["inventory_id"])

    def test_register_rejects_mismatched_passwords(self):
        response = self.register(password_confirm="Different-passphrase-42")

        self.assertEqual(response.status_code, 400)
        self.assertIn("password_confirm", response.json()["errors"])
        self.assertFalse(User.objects.filter(username="bob").exists())

    def test_register_rejects_missing_fields(self):
        response = self.register(first_name="", email="")

        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]
        self.assertIn("first_name", errors)
        self.assertIn("email", errors)

    def test_register_rejects_duplicate_username_and_email(self):
        User.objects.create_user(username="Bob", email="BOB@example.com", password="x")

        response = self.register()

        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]
        self.assertIn("username", errors)
        self.assertIn("email", errors)

    def test_register_rejects_invalid_email(self):
        response = self.register(email="not-an-email")

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])

    def test_register_rejects_weak_password(self):
        response = self.register(password="123", password_confirm="123")

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["errors"])

    def test_register_requires_post(self):
        response = self.client.get("/api/auth/register/")

        self.assertEqual(response.status_code, 405)

class InventorySwitchingTestCase(TestCase):

    def setUp(self):
        self.frontend = FrontendClient()
        self.frontend.register("switchuser")

        self.user = User.objects.get(username="switchuser")
        self.home = Inventory.objects.get(owner=self.user)
        self.office = Inventory.objects.create(
            owner=self.user,
            name="Office",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password=PASSWORD,
        )
        self.other_inventory = Inventory.objects.create(
            owner=self.other_user,
            name="Private",
        )

        Item.objects.create(
            inventory=self.home,
            name="Home Item",
            manual_value=Decimal("100.00"),
        )
        Item.objects.create(
            inventory=self.office,
            name="Office Item",
            manual_value=Decimal("900.00"),
        )

    def test_inventory_switching(self):
        response = self.frontend.post_json(
            "/api/inventories/select/",
            {"inventory_id": str(self.office.public_id)},
        )

        self.assertEqual(response.status_code, 200)

        dashboard = self.frontend.get("/api/dashboard/").json()

        self.assertEqual(
            dashboard["inventory_id"],
            str(self.office.public_id),
        )
        self.assertEqual(
            dashboard["summary"]["estimated_value"],
            900.0,
        )

        items = self.frontend.get("/api/items/").json()["items"]
        self.assertEqual(
            [item["name"] for item in items],
            ["Office Item"],
        )

    def test_cannot_select_another_users_inventory(self):
        response = self.frontend.post_json(
            "/api/inventories/select/",
            {"inventory_id": str(self.other_inventory.public_id)},
        )

        self.assertEqual(response.status_code, 404)