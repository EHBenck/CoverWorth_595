"""
Sprint 3 integration pass: the API workflow the NiceGUI frontend drives.

Register/Login -> Dashboard -> Inventory -> Add Item -> View Item -> Edit Item

Requests are sent the way the frontend sends them: session cookie auth,
CSRF token header, and form-encoded item payloads. Item deletion is not
implemented yet, so it is not covered here.
"""

import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from myapp.models import Category, Inventory, Item


User = get_user_model()

PASSWORD = "Sturdy-passphrase-42"


class FrontendClient:
    """Test client that behaves like frontend/backend_client.py."""

    def __init__(self):
        self.client = Client(enforce_csrf_checks=True)

    def csrf_headers(self):
        response = self.client.get("/api/auth/csrf/")
        return {"HTTP_X_CSRFTOKEN": response.cookies["csrftoken"].value}

    def get(self, path):
        return self.client.get(path)

    def post_json(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **self.csrf_headers(),
        )

    def post_form(self, path, payload):
        return self.client.post(path, data=payload, **self.csrf_headers())

    def register(self, username):
        return self.post_json(
            "/api/auth/register/",
            {
                "first_name": "Test",
                "last_name": "User",
                "email": f"{username}@example.com",
                "username": username,
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
        )

    def login(self, username, password=PASSWORD):
        return self.post_json(
            "/api/auth/login/",
            {"username": username, "password": password},
        )

    def logout(self):
        return self.client.post("/api/auth/logout/", **self.csrf_headers())


def valid_item(category_id, **overrides):
    return {
        "name": "Laptop",
        "category": str(category_id),
        "purchase_date": "2026-01-15",
        "purchase_amount": "1200.00",
        "description": "Work laptop",
        "brand": "Lenovo",
        "model_number": "T14",
        "serial_number": "SN-123",
        "condition": "used",
        "quantity": "1",
        "manual_value": "",
        "notes": "",
        **overrides,
    }


class FreshDatabaseTestCase(TestCase):
    def test_fresh_database_is_connected_and_empty(self):
        response = Client().get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "connected")
        self.assertEqual(response.json()["item_rows"], 0)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Inventory.objects.exists())

    def test_first_registered_user_gets_an_empty_inventory(self):
        frontend = FrontendClient()

        self.assertEqual(frontend.register("first").status_code, 201)

        response = frontend.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["inventory_id"])
        self.assertEqual(
            data["summary"],
            {
                "total_items": 0,
                "estimated_value": 0.0,
                "purchase_value": 0.0,
                "items_needing_attention": 0,
            },
        )
        self.assertEqual(data["category_data"], [])
        self.assertEqual(data["recent_items"], [])

        inventory = frontend.get(f"/api/inventory/{data['inventory_id']}/").json()
        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["items"], [])
        self.assertEqual(frontend.get("/api/items/").json(), {"items": []})


class ItemWorkflowTestCase(TestCase):
    def setUp(self):
        self.frontend = FrontendClient()
        self.assertEqual(self.frontend.register("alice").status_code, 201)
        self.inventory_id = self.frontend.get("/api/dashboard/").json()["inventory_id"]

        response = self.frontend.post_json(
            f"/api/inventory/{self.inventory_id}/categories/",
            {"name": "Electronics"},
        )
        self.assertEqual(response.status_code, 201)
        self.category = Category.objects.get(public_id=response.json()["category"]["public_id"])

    def add_item(self, **overrides):
        return self.frontend.post_form(
            f"/api/inventory/{self.inventory_id}/add-item/",
            valid_item(self.category.id, **overrides),
        )

    def test_complete_workflow_login_dashboard_inventory_add_view_edit(self):
        # Login (fresh session, as after a browser restart)
        self.frontend.logout()
        self.assertEqual(self.frontend.get("/api/dashboard/").status_code, 401)
        self.assertEqual(self.frontend.login("alice").status_code, 200)

        # Add Item form options
        options = self.frontend.get(f"/api/inventory/{self.inventory_id}/add-item/").json()
        self.assertEqual(
            options["categories"],
            [{"id": self.category.id, "name": "Electronics"}],
        )

        # Add Item
        response = self.add_item()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["success"])
        item_id = response.json()["item_id"]

        # Dashboard
        dashboard = self.frontend.get("/api/dashboard/").json()
        self.assertEqual(dashboard["summary"]["total_items"], 1)
        self.assertEqual(dashboard["summary"]["purchase_value"], 1200.0)
        self.assertEqual(dashboard["summary"]["estimated_value"], 1200.0)
        self.assertEqual(dashboard["category_data"], [{"name": "Electronics", "value": 1200.0}])
        self.assertEqual(dashboard["recent_items"][0]["public_id"], item_id)

        # Inventory
        inventory = self.frontend.get(f"/api/inventory/{self.inventory_id}/").json()
        self.assertEqual([item["public_id"] for item in inventory["items"]], [item_id])
        self.assertEqual(len(self.frontend.get("/api/items/").json()["items"]), 1)

        # View Item
        detail = self.frontend.get(f"/api/item/{item_id}/").json()
        self.assertEqual(detail["item"]["name"], "Laptop")
        self.assertEqual(detail["item"]["category"], "Electronics")
        self.assertEqual(detail["item"]["purchase_amount"], "1200.00")
        self.assertEqual(detail["inventory"]["public_id"], self.inventory_id)

        edit_view = self.frontend.get(f"/api/item/{item_id}/edit/").json()
        self.assertEqual(edit_view["item"]["category_id"], self.category.id)
        self.assertEqual(edit_view["item"]["purchase_date"], "2026-01-15")

        # Edit Item
        response = self.frontend.post_form(
            f"/api/item/{item_id}/edit/",
            valid_item(self.category.id, name="Laptop Pro", manual_value="900.00"),
        )
        self.assertEqual(response.status_code, 200, response.content)
        detail = self.frontend.get(f"/api/item/{item_id}/").json()
        self.assertEqual(detail["item"]["name"], "Laptop Pro")
        self.assertEqual(detail["item"]["manual_value"], "900.00")

        dashboard = self.frontend.get("/api/dashboard/").json()
        self.assertEqual(dashboard["summary"]["estimated_value"], 900.0)

    def test_data_persists_across_sessions(self):
        item_id = self.add_item().json()["item_id"]
        self.frontend.logout()

        other_browser = FrontendClient()
        self.assertEqual(other_browser.login("alice").status_code, 200)

        detail = other_browser.get(f"/api/item/{item_id}/").json()
        self.assertEqual(detail["item"]["name"], "Laptop")
        item = Item.objects.get(public_id=item_id)
        self.assertEqual(item.purchase_amount, Decimal("1200.00"))
        self.assertEqual(item.inventory.public_id, uuid.UUID(self.inventory_id))

    def test_manual_value_defaults_to_purchase_amount(self):
        item_id = self.add_item(manual_value="").json()["item_id"]

        self.assertEqual(Item.objects.get(public_id=item_id).manual_value, Decimal("1200.00"))

    def test_invalid_items_are_rejected_and_not_saved(self):
        cases = {
            "missing required fields": (
                {"name": "", "category": "", "purchase_date": "", "purchase_amount": ""},
                {"name", "category", "purchase_date", "purchase_amount"},
            ),
            "whitespace name": ({"name": "   "}, {"name"}),
            "bad amount": ({"purchase_amount": "abc"}, {"purchase_amount"}),
            "bad date": ({"purchase_date": "not-a-date"}, {"purchase_date"}),
            "zero quantity": ({"quantity": "0"}, {"quantity"}),
            "unknown condition": ({"condition": "broken"}, {"condition"}),
            "unknown category": ({"category": "999999"}, {"category"}),
        }

        for label, (overrides, expected_fields) in cases.items():
            with self.subTest(label):
                response = self.add_item(**overrides)

                self.assertEqual(response.status_code, 400, response.content)
                data = response.json()
                self.assertFalse(data["success"])
                self.assertTrue(expected_fields <= set(data["errors"]), data["errors"])

        self.assertFalse(Item.objects.exists())

    def test_negative_amount_is_rejected(self):
        response = self.add_item(purchase_amount="-5")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Item.objects.exists())

    def test_category_from_another_inventory_is_rejected(self):
        other = User.objects.create_user(username="mallory", password=PASSWORD)
        other_inventory = Inventory.objects.create(owner=other, name="Other")
        other_category = Category.objects.create(inventory=other_inventory, name="Theirs")

        response = self.add_item(category=str(other_category.id))

        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.json()["errors"])

    def test_invalid_edit_keeps_the_original_item(self):
        item_id = self.add_item().json()["item_id"]

        response = self.frontend.post_form(
            f"/api/item/{item_id}/edit/",
            valid_item(self.category.id, name="", purchase_amount="abc"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Item.objects.get(public_id=item_id).name, "Laptop")

    def test_deleting_a_category_uncategorizes_its_items(self):
        item_id = self.add_item().json()["item_id"]

        response = self.frontend.client.delete(
            f"/api/category/{self.category.public_id}/",
            **self.frontend.csrf_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items_uncategorized"], 1)
        detail = self.frontend.get(f"/api/item/{item_id}/").json()
        self.assertEqual(detail["item"]["category"], "Uncategorized")
        self.assertEqual(
            self.frontend.get(f"/api/inventory/{self.inventory_id}/categories/").json()["categories"],
            [],
        )


class MissingResourceTestCase(TestCase):
    def setUp(self):
        self.frontend = FrontendClient()
        self.frontend.register("alice")
        self.missing = uuid.uuid4()

    def test_missing_resources_return_json_404(self):
        paths = [
            f"/api/item/{self.missing}/",
            f"/api/item/{self.missing}/edit/",
            f"/api/inventory/{self.missing}/",
            f"/api/inventory/{self.missing}/add-item/",
        ]
        for path in paths:
            with self.subTest(path):
                response = self.frontend.get(path)

                self.assertEqual(response.status_code, 404)
                self.assertFalse(response.json()["success"])

    def test_posting_to_missing_resources_returns_404(self):
        paths = [
            f"/api/item/{self.missing}/edit/",
            f"/api/inventory/{self.missing}/add-item/",
        ]
        for path in paths:
            with self.subTest(path):
                response = self.frontend.post_form(path, {"name": "Ghost"})

                self.assertEqual(response.status_code, 404)

    def test_missing_category_returns_404(self):
        self.assertEqual(self.frontend.get(f"/api/category/{self.missing}/").status_code, 404)

    def test_malformed_ids_do_not_match_any_route(self):
        self.assertEqual(self.frontend.get("/api/item/not-a-uuid/").status_code, 404)
        self.assertEqual(self.frontend.get("/api/inventory/None/add-item/").status_code, 404)


class BasicApiErrorTestCase(TestCase):
    def setUp(self):
        self.owner = FrontendClient()
        self.owner.register("alice")
        inventory = Inventory.objects.get(owner__username="alice")
        category = Category.objects.create(inventory=inventory, name="Art")
        self.item = Item.objects.create(
            inventory=inventory,
            category=category,
            name="Painting",
            purchase_amount=Decimal("50.00"),
        )
        self.inventory = inventory
        self.category = category

    def protected_paths(self):
        return [
            "/api/dashboard/",
            "/api/items/",
            f"/api/inventory/{self.inventory.public_id}/",
            f"/api/inventory/{self.inventory.public_id}/add-item/",
            f"/api/inventory/{self.inventory.public_id}/categories/",
            f"/api/item/{self.item.public_id}/",
            f"/api/item/{self.item.public_id}/edit/",
            f"/api/category/{self.category.public_id}/",
        ]

    def test_endpoints_require_authentication(self):
        anonymous = Client()
        for path in self.protected_paths():
            with self.subTest(path):
                self.assertEqual(anonymous.get(path).status_code, 401)

    def test_other_users_cannot_read_or_change_data(self):
        intruder = FrontendClient()
        intruder.register("mallory")

        # Item detail answers 404 so it does not reveal that the item exists.
        for path in self.protected_paths()[2:]:
            with self.subTest(path):
                expected_status = (
                    404
                    if path == f"/api/item/{self.item.public_id}/"
                    else 403
                )
                self.assertEqual(intruder.get(path).status_code, expected_status)

        response = intruder.post_form(
            f"/api/item/{self.item.public_id}/edit/",
            valid_item(self.category.id, name="Stolen"),
        )
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Painting")

    def test_state_changing_requests_require_csrf_token(self):
        response = self.owner.client.post(
            f"/api/inventory/{self.inventory.public_id}/add-item/",
            data=valid_item(self.category.id),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Item.objects.count(), 1)

    def test_malformed_json_returns_400(self):
        for path in [
            "/api/auth/login/",
            "/api/auth/register/",
            f"/api/inventory/{self.inventory.public_id}/categories/",
        ]:
            with self.subTest(path):
                response = self.owner.client.post(
                    path,
                    data="{not json",
                    content_type="application/json",
                    **self.owner.csrf_headers(),
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())

    def test_unsupported_methods_return_405(self):
        cases = [
            ("put", f"/api/item/{self.item.public_id}/"),
            ("delete", f"/api/item/{self.item.public_id}/"),
            ("put", f"/api/inventory/{self.inventory.public_id}/add-item/"),
            ("get", "/api/auth/logout/"),
        ]
        for method, path in cases:
            with self.subTest(f"{method.upper()} {path}"):
                response = getattr(self.owner.client, method)(path, **self.owner.csrf_headers())
                self.assertEqual(response.status_code, 405)

    def test_expired_session_is_rejected(self):
        self.owner.logout()

        self.assertEqual(self.owner.get("/api/dashboard/").status_code, 401)
