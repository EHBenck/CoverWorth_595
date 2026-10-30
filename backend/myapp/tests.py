import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from myapp.models import Attachment, Category, Inventory, Item, Location, ValuationRun
from myapp.test_integration import FrontendClient, PASSWORD


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


class AccountSettingsAPITestCase(TestCase):
    PASSWORD = "Sturdy-passphrase-42"
    NEW_PASSWORD = "Fresh-passphrase-77"

    def setUp(self):
        self.user = User.objects.create_user(
            username="carol",
            email="carol@example.com",
            password=self.PASSWORD,
            first_name="Carol",
            last_name="Jones",
        )
        self.other = User.objects.create_user(
            username="dave",
            email="dave@example.com",
            password=self.PASSWORD,
            first_name="Dave",
            last_name="Brown",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def _write(self, method, path, payload=None, *, client=None):
        client = client or self.client
        token = client.get("/api/auth/csrf/").cookies["csrftoken"].value
        return getattr(client, method)(
            path,
            data=payload if isinstance(payload, str) else json.dumps({} if payload is None else payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def _update(self, payload, **kwargs):
        return self._write("patch", "/api/account/", payload, **kwargs)

    def _change_password(self, **overrides):
        payload = {
            "current_password": self.PASSWORD,
            "new_password": self.NEW_PASSWORD,
            "new_password_confirm": self.NEW_PASSWORD,
            **overrides,
        }
        return self._write("post", "/api/account/password/", payload)

    def test_account_returns_signed_in_users_profile(self):
        response = self.client.get("/api/account/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account"], {
            "first_name": "Carol",
            "last_name": "Jones",
            "email": "carol@example.com",
            "username": "carol",
        })

    def test_owner_can_update_names_and_email(self):
        response = self._update({
            "first_name": "  Caroline ",
            "last_name": "Smith",
            "email": " caroline@example.com ",
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["account"]["email"], "caroline@example.com")
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.first_name, self.user.last_name, self.user.email, self.user.username),
            ("Caroline", "Smith", "caroline@example.com", "carol"),
        )

    def test_partial_update_preserves_other_fields(self):
        response = self._update({"last_name": "Taylor"})

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.first_name, self.user.last_name, self.user.email),
            ("Carol", "Taylor", "carol@example.com"),
        )

    def test_user_can_keep_own_email_with_different_case(self):
        response = self._update({"email": "CAROL@example.com"})

        self.assertEqual(response.status_code, 200, response.content)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        response = self._update({"first_name": "Changed", "email": " DAVE@example.com "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ("Carol", "carol@example.com"))

    def test_invalid_blank_and_too_long_fields_are_rejected_without_changes(self):
        for payload, field in [
            ({"email": "not-an-email"}, "email"),
            ({"email": "   "}, "email"),
            ({"first_name": ""}, "first_name"),
            ({"last_name": 42}, "last_name"),
            ({"first_name": "x" * 151}, "first_name"),
        ]:
            with self.subTest(payload=payload):
                response = self._update(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.first_name, self.user.last_name, self.user.email),
            ("Carol", "Jones", "carol@example.com"),
        )

    def test_unknown_fields_cannot_change_username_or_another_account(self):
        for payload in [
            {"username": "mallory"},
            {"id": self.other.pk, "first_name": "Hacked"},
            {"is_staff": True},
            {},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self._update(payload).status_code, 400)
        self.assertEqual(self._update("[]").status_code, 400)
        self.assertEqual(self._update("{bad json").status_code, 400)

        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.user.username, self.user.is_staff), ("carol", False))
        self.assertEqual(self.other.first_name, "Dave")

    def test_update_only_changes_the_signed_in_account(self):
        self._update({"first_name": "Caroline"})

        self.other.refresh_from_db()
        self.assertEqual(self.other.first_name, "Dave")

    def test_account_endpoints_require_authentication(self):
        anonymous = Client()
        self.assertEqual(anonymous.get("/api/account/").status_code, 401)
        self.assertEqual(
            self._update({"first_name": "X"}, client=anonymous).status_code, 401
        )
        self.assertEqual(
            self._write("post", "/api/account/password/", {}, client=anonymous).status_code, 401
        )

    def test_account_writes_require_csrf_and_correct_methods(self):
        self.assertEqual(
            self.client.patch("/api/account/", data='{"first_name":"X"}', content_type="application/json").status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/account/password/", data="{}", content_type="application/json").status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/account/password/").status_code, 405)
        self.assertEqual(self._write("post", "/api/account/", {"first_name": "X"}).status_code, 405)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Carol")

    def test_password_change_uses_django_hashing_and_keeps_session(self):
        response = self._change_password()

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.NEW_PASSWORD))
        self.assertNotEqual(self.user.password, self.NEW_PASSWORD)
        self.assertEqual(self.client.get("/api/account/").status_code, 200)

        fresh = Client()
        self.assertEqual(
            fresh.post(
                "/api/auth/login/",
                data={"username": "carol", "password": self.PASSWORD},
                content_type="application/json",
            ).status_code,
            401,
        )
        self.assertEqual(
            fresh.post(
                "/api/auth/login/",
                data={"username": "carol", "password": self.NEW_PASSWORD},
                content_type="application/json",
            ).status_code,
            200,
        )

    def test_password_change_signs_out_other_sessions(self):
        other_session = Client()
        other_session.force_login(self.user)

        self.assertEqual(self._change_password().status_code, 200)

        self.assertEqual(other_session.get("/api/account/").status_code, 401)

    def test_password_change_validation(self):
        for overrides, field in [
            ({"current_password": "wrong-secret"}, "current_password"),
            ({"current_password": ""}, "current_password"),
            ({"new_password_confirm": "Different-passphrase-1"}, "new_password_confirm"),
            ({"new_password": "", "new_password_confirm": ""}, "new_password"),
            ({"new_password": "short", "new_password_confirm": "short"}, "new_password"),
            ({"new_password": "12345678901", "new_password_confirm": "12345678901"}, "new_password"),
            ({"new_password": "password123", "new_password_confirm": "password123"}, "new_password"),
            ({"new_password": "carolexample", "new_password_confirm": "carolexample"}, "new_password"),
            ({"new_password": self.PASSWORD, "new_password_confirm": self.PASSWORD}, "new_password"),
        ]:
            with self.subTest(overrides=overrides):
                response = self._change_password(**overrides)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.PASSWORD))

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

class InventoryManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="inventory-owner", password="test-password")
        cls.other_user = User.objects.create_user(username="inventory-other", password="test-password")
        cls.foreign = Inventory.objects.create(owner=cls.other_user, name="Private inventory")
        cls.home = Inventory.objects.create(
            owner=cls.owner, name="Home", description="Belongings at home",
        )
        cls.office = Inventory.objects.create(owner=cls.owner, name="Office")
        cls.archived = Inventory.objects.create(
            owner=cls.owner, name="Old home", archived_at=timezone.now(),
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)
        self._set_active(self.home)

    def _set_active(self, inventory):
        session = self.client.session
        session["active_inventory_id"] = str(inventory.public_id)
        session.save()

    def _write(self, method, path, payload=None, *, client=None):
        client = client or self.client
        token = client.get("/api/auth/csrf/").cookies["csrftoken"].value
        return getattr(client, method)(
            path,
            data=json.dumps({} if payload is None else payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def _update(self, inventory, payload, **kwargs):
        return self._write("patch", f"/api/inventories/{inventory.public_id}/", payload, **kwargs)

    def _archive(self, inventory, **kwargs):
        return self._write("post", f"/api/inventories/{inventory.public_id}/archive/", **kwargs)

    def test_owner_can_rename_and_update_description_without_switching(self):
        response = self._update(self.office, {"name": "  Work equipment  ", "description": "Company laptop\nDesk"})
        self.assertEqual(response.status_code, 200, response.content)
        self.office.refresh_from_db()
        self.assertEqual(self.office.name, "Work equipment")
        self.assertEqual(self.office.description, "Company laptop\nDesk")
        self.assertEqual(response.json()["inventory"]["public_id"], str(self.office.public_id))
        self.assertEqual(response.json()["active_inventory_id"], str(self.home.public_id))
        listed = self.client.get("/api/inventories/").json()["inventories"]
        self.assertIn("Work equipment", [row["name"] for row in listed])

    def test_partial_update_preserves_other_fields_and_can_clear_description(self):
        response = self._update(self.home, {"name": "Family home"})
        self.assertEqual(response.status_code, 200, response.content)
        self.home.refresh_from_db()
        self.assertEqual(self.home.description, "Belongings at home")
        response = self._update(self.home, {"description": ""})
        self.assertEqual(response.status_code, 200, response.content)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Family home")
        self.assertEqual(self.home.description, "")
        self.assertEqual(self.home.default_currency, "USD")
        self.assertEqual(self.home.owner_id, self.owner.pk)

    def test_invalid_fields_are_rejected_without_partial_updates(self):
        cases = [
            {"name": ""}, {"name": " \t\n "}, {"name": "x" * 256},
            {"name": None}, {"name": 42}, {"description": None},
            {"description": []}, {"name": "Changed", "description": False},
            {}, ["not", "an", "object"],
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                response = self._update(self.home, payload)
                self.assertEqual(response.status_code, 400, response.content)
                self.home.refresh_from_db()
                self.assertEqual(self.home.name, "Home")
                self.assertEqual(self.home.description, "Belongings at home")

    def test_duplicate_active_name_is_case_insensitive_and_trimmed(self):
        for name in ["Office", "office", "  OFFICE  "]:
            with self.subTest(name=name):
                response = self._update(self.home, {"name": name})
                self.assertEqual(response.status_code, 400, response.content)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Home")

    def test_name_can_match_own_current_name_foreign_name_or_archived_name(self):
        for name in ["Home", "Private inventory", "Old home"]:
            with self.subTest(name=name):
                response = self._update(self.home, {"name": name})
                self.assertEqual(response.status_code, 200, response.content)

    def test_patch_cannot_change_owner_uuid_or_archive_state(self):
        for field, value in [
            ("owner", self.other_user.pk), ("owner_id", self.other_user.pk),
            ("public_id", str(uuid4())), ("archived_at", timezone.now().isoformat()),
            ("default_currency", "EUR"),
        ]:
            with self.subTest(field=field):
                response = self._update(self.home, {"name": "Changed", field: value})
                self.assertEqual(response.status_code, 400, response.content)
        self.home.refresh_from_db()
        self.assertEqual(self.home.owner_id, self.owner.pk)
        self.assertEqual(self.home.name, "Home")
        self.assertIsNone(self.home.archived_at)

    def test_anonymous_requests_require_authentication(self):
        anonymous = Client(enforce_csrf_checks=True)
        self.assertEqual(self._update(self.home, {"name": "Changed"}, client=anonymous).status_code, 401)
        self.assertEqual(self._archive(self.home, client=anonymous).status_code, 401)

    def test_another_users_inventory_cannot_be_modified(self):
        self.assertEqual(self._update(self.foreign, {"name": "Stolen", "description": "Changed"}).status_code, 404)
        self.assertEqual(self._archive(self.foreign).status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.name, "Private inventory")
        self.assertEqual(self.foreign.description, "")
        self.assertIsNone(self.foreign.archived_at)
        self.assertEqual(self.client.session["active_inventory_id"], str(self.home.public_id))

    def test_missing_and_malformed_inventory_identifiers_do_not_mutate_anything(self):
        for identifier in [str(uuid4()), "not-a-uuid", str(self.home.pk)]:
            with self.subTest(identifier=identifier):
                self.assertEqual(self._write("patch", f"/api/inventories/{identifier}/", {"name": "Changed"}).status_code, 404)
                self.assertEqual(self._write("post", f"/api/inventories/{identifier}/archive/").status_code, 404)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Home")
        self.assertIsNone(self.home.archived_at)

    def test_archived_inventory_cannot_be_edited_or_archived_again(self):
        previous_time = self.archived.archived_at
        self.assertEqual(self._update(self.archived, {"name": "Changed"}).status_code, 404)
        self.assertEqual(self._archive(self.archived).status_code, 404)
        self.archived.refresh_from_db()
        self.assertEqual(self.archived.name, "Old home")
        self.assertEqual(self.archived.archived_at, previous_time)

    def test_management_writes_require_csrf_and_do_not_accept_get(self):
        for method, path in [
            ("patch", f"/api/inventories/{self.home.public_id}/"),
            ("post", f"/api/inventories/{self.home.public_id}/archive/"),
        ]:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path, data='{"name":"Changed"}', content_type="application/json")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.client.get(path).status_code, 405)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Home")
        self.assertIsNone(self.home.archived_at)

    def test_invalid_json_is_a_validation_error(self):
        token = self.client.get("/api/auth/csrf/").cookies["csrftoken"].value
        response = self.client.patch(
            f"/api/inventories/{self.home.public_id}/", data="{invalid",
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Home")

    def test_archive_preserves_inventory_items_and_categories(self):
        category = Category.objects.create(inventory=self.office, name="Electronics")
        item = Item.objects.create(
            inventory=self.office, category=category, name="Laptop",
            quantity=1, manual_value=Decimal("500.00"),
        )
        response = self._archive(self.office)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["archived_inventory_id"], str(self.office.public_id))
        self.office.refresh_from_db()
        item.refresh_from_db()
        category.refresh_from_db()
        self.assertIsNotNone(self.office.archived_at)
        self.assertEqual(self.office.name, "Office")
        self.assertEqual(item.inventory_id, self.office.pk)
        self.assertEqual(item.category_id, category.pk)
        self.assertEqual(item.manual_value, Decimal("500.00"))
        self.assertIsNone(item.archived_at)
        self.assertIsNone(category.archived_at)

    def test_archiving_selected_inventory_selects_oldest_usable_owned_inventory(self):
        Inventory.objects.create(owner=self.owner, name="Garage")
        self._set_active(self.office)
        response = self._archive(self.office)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["active_inventory_id"], str(self.home.public_id))
        self.assertEqual(self.client.session["active_inventory_id"], str(self.home.public_id))
        self.assertEqual(self.client.get("/api/dashboard/").json()["inventory_id"], str(self.home.public_id))

    def test_archiving_different_inventory_keeps_current_selection(self):
        self._set_active(self.office)
        response = self._archive(self.home)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["active_inventory_id"], str(self.office.public_id))
        self.assertEqual(self.client.session["active_inventory_id"], str(self.office.public_id))

    def test_last_usable_inventory_cannot_be_archived_even_with_other_users_or_archived_inventories(self):
        Inventory.objects.filter(pk=self.office.pk).update(archived_at=timezone.now())
        before_count = Inventory.objects.filter(owner=self.owner).count()
        response = self._archive(self.home)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertTrue(response.json().get("error"))
        self.home.refresh_from_db()
        self.assertIsNone(self.home.archived_at)
        self.assertEqual(Inventory.objects.filter(owner=self.owner).count(), before_count)
        self.assertEqual(self.client.session["active_inventory_id"], str(self.home.public_id))

    def test_archived_inventories_disappear_from_switcher_and_cannot_be_selected(self):
        self.assertEqual(self._archive(self.office).status_code, 200)
        payload = self.client.get("/api/inventories/").json()
        self.assertEqual([row["public_id"] for row in payload["inventories"]], [str(self.home.public_id)])
        response = self._write("post", "/api/inventories/select/", {"inventory_id": str(self.office.public_id)})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.session["active_inventory_id"], str(self.home.public_id))

    def test_other_logged_in_session_recovers_after_its_inventory_is_archived(self):
        other_session = Client(enforce_csrf_checks=True)
        other_session.force_login(self.owner)
        session = other_session.session
        session["active_inventory_id"] = str(self.office.public_id)
        session.save()
        self.assertEqual(self._archive(self.office).status_code, 200)
        payload = other_session.get("/api/inventories/").json()
        self.assertEqual(payload["active_inventory_id"], str(self.home.public_id))
        self.assertEqual(other_session.session["active_inventory_id"], str(self.home.public_id))
        self.assertEqual(other_session.get("/api/dashboard/").json()["inventory_id"], str(self.home.public_id))

    def test_existing_create_and_switch_can_supply_replacement_for_last_inventory(self):
        self.assertEqual(self._archive(self.office).status_code, 200)
        self.assertEqual(self._archive(self.home).status_code, 409)
        response = self._write("post", "/api/inventories/", {"name": "Replacement", "description": "New place"})
        self.assertEqual(response.status_code, 201, response.content)
        replacement_id = response.json()["inventory"]["public_id"]
        self.assertEqual(response.json()["active_inventory_id"], replacement_id)
        self.assertEqual(self._write("post", "/api/inventories/select/", {"inventory_id": str(self.home.public_id)}).status_code, 200)
        archived = self._archive(self.home)
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertEqual(archived.json()["active_inventory_id"], replacement_id)
        self.assertEqual(len(self.client.get("/api/inventories/").json()["inventories"]), 1)

    def test_archived_inventory_is_not_accessible_through_stale_child_urls(self):
        category = Category.objects.create(inventory=self.office, name="Electronics")
        item = Item.objects.create(inventory=self.office, category=category, name="Laptop")
        attachment = Attachment.objects.create(item=item, file="existing-receipt.pdf", file_type="receipt")
        self.assertEqual(self._archive(self.office).status_code, 200)
        paths = [
            f"/api/inventory/{self.office.public_id}/",
            f"/api/inventory/{self.office.public_id}/add-item/",
            f"/api/inventory/{self.office.public_id}/categories/",
            f"/api/item/{item.public_id}/",
            f"/api/item/{item.public_id}/edit/",
            f"/api/item/{item.public_id}/attachments/",
            f"/api/category/{category.public_id}/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        for method, path in [
            ("post", f"/api/inventory/{self.office.public_id}/add-item/"),
            ("post", f"/api/inventory/{self.office.public_id}/categories/"),
            ("post", f"/api/item/{item.public_id}/edit/"),
            ("delete", f"/api/item/{item.public_id}/edit/"),
            ("post", f"/api/item/{item.public_id}/attachments/"),
            ("delete", f"/api/attachment/{attachment.public_id}/"),
            ("put", f"/api/category/{category.public_id}/"),
            ("delete", f"/api/category/{category.public_id}/"),
        ]:
            with self.subTest(method=method, path=path):
                self.assertEqual(self._write(method, path, {"name": "Changed"}).status_code, 404)
        item.refresh_from_db()
        category.refresh_from_db()
        attachment.refresh_from_db()
        self.assertEqual(item.name, "Laptop")
        self.assertEqual(category.name, "Electronics")
        self.assertIsNone(item.archived_at)
        self.assertIsNone(category.archived_at)
        self.assertIsNone(attachment.archived_at)
        self.assertEqual(attachment.file.name, "existing-receipt.pdf")

    def test_archived_inventory_rejects_valuations_before_external_requests(self):
        item = Item.objects.create(inventory=self.office, name="Laptop")
        self.assertEqual(self._archive(self.office).status_code, 200)
        with patch("myapp.views.search_ebay") as external_search:
            response = self._write("post", f"/api/item/{item.public_id}/valuation/")
            self.assertEqual(response.status_code, 404)
            external_search.assert_not_called()
        response = self._write("post", f"/api/item/{item.public_id}/valuation/accept/", {"valuation_run_id": str(uuid4())})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(item.valuation_runs.exists())

    def test_archived_inventory_keeps_valuations_but_blocks_history_and_acceptance(self):
        item = Item.objects.create(
            inventory=self.office, name="Laptop", current_estimated_amount=Decimal("100.00"),
        )
        valuation = ValuationRun.objects.create(
            item=item, requested_by=self.owner, status="success",
            estimated_amount=Decimal("250.00"), sample_count=3,
        )
        history_path = f"/api/item/{item.public_id}/valuation/history/"
        before = self.client.get(history_path)
        self.assertEqual(before.status_code, 200, before.content)
        self.assertEqual(before.json()["history"][0]["valuation_run_id"], str(valuation.public_id))

        self.assertEqual(self._archive(self.office).status_code, 200)
        self.assertEqual(self.client.get(history_path).status_code, 404)
        response = self._write(
            "post", f"/api/item/{item.public_id}/valuation/accept/",
            {"valuation_run_id": str(valuation.public_id)},
        )
        self.assertEqual(response.status_code, 404, response.content)
        item.refresh_from_db()
        valuation.refresh_from_db()
        self.assertEqual(item.current_estimated_amount, Decimal("100.00"))
        self.assertIsNone(item.valuation_date)
        self.assertEqual(valuation.item_id, item.pk)
        self.assertEqual(valuation.estimated_amount, Decimal("250.00"))
        self.assertEqual(valuation.status, "success")

    def test_sqlite_authentication_lock_returns_retryable_error_for_inventory_requests(self):
        if connections["default"].vendor != "sqlite":
            self.skipTest("SQLite-specific authentication lock contention")
        token = self.client.get("/api/auth/csrf/").cookies["csrftoken"].value
        before_count = Inventory.objects.filter(owner=self.owner).count()
        requests = [
            ("get", "/api/inventories/", None),
            ("post", "/api/inventories/", {"name": "Blocked creation"}),
            ("patch", f"/api/inventories/{self.office.public_id}/", {"name": "Changed"}),
            ("post", f"/api/inventories/{self.office.public_id}/archive/", {}),
        ]
        for method, path, payload in requests:
            with self.subTest(method=method, path=path):
                request_kwargs = {"HTTP_X_CSRFTOKEN": token}
                if method != "get":
                    request_kwargs.update(data=json.dumps(payload), content_type="application/json")
                # A competing archive may lock auth_user before this request's
                # lazy request.user lookup runs. Return a retryable error.
                with patch(
                    "django.contrib.auth.get_user",
                    side_effect=OperationalError("database table is locked: auth_user"),
                ):
                    response = getattr(self.client, method)(path, **request_kwargs)
                self.assertEqual(response.status_code, 409, response.content)
                self.assertFalse(response.json()["success"])
        self.office.refresh_from_db()
        self.assertEqual(self.office.name, "Office")
        self.assertIsNone(self.office.archived_at)
        self.assertEqual(Inventory.objects.filter(owner=self.owner).count(), before_count)
        self.assertEqual(self.client.session["active_inventory_id"], str(self.home.public_id))


class ConcurrentInventoryArchiveTests(TransactionTestCase):
    """Two simultaneous archive requests must never consume the last inventory."""

    def test_competing_archives_leave_one_usable_inventory(self):
        owner = get_user_model().objects.create_user(username="concurrent-owner")
        inventories = [
            Inventory.objects.create(owner=owner, name="First"),
            Inventory.objects.create(owner=owner, name="Second"),
        ]
        requests = []
        for inventory in inventories:
            client = Client(enforce_csrf_checks=True, raise_request_exception=False)
            client.force_login(owner)
            token = client.get("/api/auth/csrf/").cookies["csrftoken"].value
            requests.append((client, inventory.public_id, token))

        start = Barrier(2)

        def archive(request):
            client, inventory_id, token = request
            connections.close_all()
            try:
                start.wait(timeout=10)
                response = client.post(
                    f"/api/inventories/{inventory_id}/archive/",
                    data="{}", content_type="application/json", HTTP_X_CSRFTOKEN=token,
                )
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(archive, requests))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(Inventory.objects.filter(owner=owner, archived_at__isnull=True).count(), 1)
        self.assertEqual(Inventory.objects.filter(owner=owner).count(), 2)


class POCRegressionTests(TestCase):
    """API regressions found while exercising existing inventory workflows."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="poc-regression-owner")
        cls.inventory = Inventory.objects.create(owner=cls.owner, name="Main")
        cls.category = Category.objects.create(inventory=cls.inventory, name="Equipment")
        cls.item = Item.objects.create(
            inventory=cls.inventory, category=cls.category, name="Camera",
            purchase_amount=Decimal("0.00"), manual_value=Decimal("0.00"),
        )
        cls.unpriced_item = Item.objects.create(inventory=cls.inventory, name="Unpriced")

    def setUp(self):
        self.media_root = self.enterContext(TemporaryDirectory(prefix="coverworth-poc-media-"))
        self.enterContext(override_settings(MEDIA_ROOT=self.media_root))
        self.client = Client(enforce_csrf_checks=True, raise_request_exception=False)
        self.client.force_login(self.owner)
        self.csrf_token = self.client.get("/api/auth/csrf/").cookies["csrftoken"].value
        self.client.get("/api/inventories/")

    def _write_json(self, method, path, payload):
        return getattr(self.client, method)(
            path, data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def _recent_item(self, item):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        return next(row for row in response.json()["recent_items"] if row["public_id"] == str(item.public_id))

    def test_inventory_creation_rejects_whitespace_without_changing_selection(self):
        response = self._write_json("post", "/api/inventories/", {"name": " \t\n "})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("name", response.json()["errors"])
        self.assertEqual(Inventory.objects.filter(owner=self.owner).count(), 1)
        self.assertEqual(self.client.session["active_inventory_id"], str(self.inventory.public_id))

    def test_inventory_creation_validates_trimmed_name_length(self):
        name = "a" * 255
        response = self._write_json("post", "/api/inventories/", {"name": f"  {name}  "})
        self.assertEqual(response.status_code, 201, response.content)
        created = Inventory.objects.get(public_id=response.json()["inventory"]["public_id"])
        self.assertEqual(created.name, name)

    def test_category_writes_reject_nonobject_json_without_changes(self):
        paths = [
            ("post", f"/api/inventory/{self.inventory.public_id}/categories/"),
            ("put", f"/api/category/{self.category.public_id}/"),
        ]
        for method, path in paths:
            for payload in ([], "category", 17, True, None):
                with self.subTest(method=method, payload=payload):
                    response = self._write_json(method, path, payload)
                    self.assertEqual(response.status_code, 400, response.content[:200])
                    self.assertFalse(response.json()["success"])
                    self.assertIn("error", response.json())
                    self.assertEqual(Category.objects.filter(inventory=self.inventory).count(), 1)
                    self.category.refresh_from_db()
                    self.assertEqual(self.category.name, "Equipment")

    def test_item_edit_preserves_zero_and_missing_purchase_manual_amounts(self):
        for item, expected in ((self.item, "0.00"), (self.unpriced_item, None)):
            with self.subTest(item=item.name):
                response = self.client.get(f"/api/item/{item.public_id}/edit/")
                self.assertEqual(response.status_code, 200)
                payload = response.json()["item"]
                self.assertEqual(payload["purchase_amount"], expected)
                self.assertEqual(payload["manual_value"], expected)

    def test_inventory_detail_preserves_zero_and_missing_purchase_manual_amounts(self):
        response = self.client.get(f"/api/inventory/{self.inventory.public_id}/")
        self.assertEqual(response.status_code, 200)
        rows = {row["public_id"]: row for row in response.json()["items"]}
        for item, expected in ((self.item, "0.00"), (self.unpriced_item, None)):
            with self.subTest(item=item.name):
                self.assertEqual(rows[str(item.public_id)]["purchase_amount"], expected)
                self.assertEqual(rows[str(item.public_id)]["manual_value"], expected)

    def test_attachment_delete_rejects_archived_item_without_mutating_attachment(self):
        attachment = Attachment.objects.create(item=self.item, file="poc/receipt.pdf", file_type="receipt")
        self.item.archived_at = timezone.now()
        self.item.save(update_fields=["archived_at"])
        response = self.client.delete(
            f"/api/attachment/{attachment.public_id}/", HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(response.status_code, 404, response.content)
        attachment.refresh_from_db()
        self.assertIsNone(attachment.archived_at)

    def test_dashboard_receipt_only_item_has_no_photo_thumbnail(self):
        Attachment.objects.create(item=self.item, file="poc/receipt.pdf", file_type="receipt")
        self.assertIsNone(self._recent_item(self.item)["image_url"])

    def test_dashboard_uses_active_primary_photo_instead_of_receipt_or_archived_photo(self):
        Attachment.objects.create(item=self.item, file="poc/receipt.pdf", file_type="receipt")
        Attachment.objects.create(item=self.item, file="poc/secondary.png", file_type="photo")
        primary = Attachment.objects.create(
            item=self.item, file="poc/primary.png", file_type="photo", is_primary=True,
        )
        Attachment.objects.create(
            item=self.item, file="poc/archived.png", file_type="photo",
            is_primary=True, archived_at=timezone.now(),
        )
        response = self.client.get(f"/api/item/{self.item.public_id}/attachments/")
        self.assertEqual(response.status_code, 200)
        expected_url = next(row["file_url"] for row in response.json()["attachments"] if row["public_id"] == str(primary.public_id))
        self.assertEqual(self._recent_item(self.item)["image_url"], expected_url)

    def test_inventory_detail_exposes_persisted_locations_and_missing_location(self):
        office = Location.objects.create(inventory=self.inventory, name="Office")
        attic = Location.objects.create(inventory=self.inventory, name="Attic")
        self.item.location = office
        self.item.save(update_fields=["location"])
        attic_item = Item.objects.create(inventory=self.inventory, name="Lamp", location=attic)
        response = self.client.get(f"/api/inventory/{self.inventory.public_id}/")
        self.assertEqual(response.status_code, 200)
        rows = {row["public_id"]: row for row in response.json()["items"]}
        self.assertEqual(rows[str(self.item.public_id)]["location"], "Office")
        self.assertEqual(rows[str(attic_item.public_id)]["location"], "Attic")
        self.assertIsNone(rows[str(self.unpriced_item.public_id)]["location"])

    def _upload_attachment(self, name="photo.png", content=b"\x89PNG\r\n\x1a\nphoto", mime_type="image/png", file_type="photo"):
        response = self.client.post(
            f"/api/item/{self.item.public_id}/attachments/",
            {"file": SimpleUploadedFile(name, content, content_type=mime_type), "file_type": file_type},
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["attachment"]
        return Attachment.objects.get(public_id=data["public_id"]), data

    def test_all_attachment_urls_use_the_authenticated_file_route(self):
        attachment, uploaded = self._upload_attachment()
        expected = reverse("attachment-file", kwargs={"attachment_id": attachment.public_id})
        self.assertEqual(uploaded["file_url"], expected)
        listing = self.client.get(f"/api/item/{self.item.public_id}/attachments/").json()
        self.assertEqual(listing["attachments"][0]["file_url"], expected)
        self.assertEqual(self._recent_item(self.item)["image_url"], expected)
        inventory = self.client.get(f"/api/inventory/{self.inventory.public_id}/").json()
        row = next(item for item in inventory["items"] if item["public_id"] == str(self.item.public_id))
        self.assertEqual(row["primary_photo_url"], expected)

    def test_owner_can_get_and_head_attachment_with_private_safe_headers(self):
        content = b"\x89PNG\r\n\x1a\nexact photo bytes"
        attachment, _ = self._upload_attachment(content=content)
        path = f"/api/attachment/{attachment.public_id}/file/"
        response = self.client.get(path)
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), content)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        head = self.client.head(path)
        self.addCleanup(head.close)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head["Content-Length"], str(len(content)))
        self.assertEqual(head["Content-Type"], "image/png")
        self.assertEqual(b"".join(head.streaming_content), b"")

    def test_attachment_download_requires_the_owner_for_get_and_head(self):
        attachment, _ = self._upload_attachment()
        path = f"/api/attachment/{attachment.public_id}/file/"
        other = Client()
        other.force_login(User.objects.create_user(username="poc-other-owner"))
        for client, expected in ((Client(), 401), (other, 404)):
            for method in ("get", "head"):
                with self.subTest(expected=expected, method=method):
                    self.assertEqual(getattr(client, method)(path).status_code, expected)

    def test_attachment_download_rejects_archived_attachment_item_or_inventory(self):
        attachment, _ = self._upload_attachment()
        path = f"/api/attachment/{attachment.public_id}/file/"
        for archived in (attachment, self.item, self.inventory):
            with self.subTest(archived_model=type(archived).__name__):
                archived.archived_at = timezone.now()
                archived.save(update_fields=["archived_at"])
                try:
                    self.assertEqual(self.client.get(path).status_code, 404)
                    self.assertEqual(self.client.head(path).status_code, 404)
                finally:
                    archived.archived_at = None
                    archived.save(update_fields=["archived_at"])

    def test_attachment_download_missing_record_or_file_returns_json_404(self):
        missing = Attachment.objects.create(item=self.item, file="missing/not-there.png", file_type="photo")
        empty = Attachment.objects.create(item=self.item, file="", file_type="other")
        for public_id in (uuid4(), missing.public_id, empty.public_id):
            with self.subTest(public_id=public_id):
                response = self.client.get(f"/api/attachment/{public_id}/file/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertIn("error", response.json())

    def test_untrusted_html_and_svg_are_downloads_even_with_image_metadata(self):
        samples = [
            ("unsafe.html", b"<html><script>alert(1)</script></html>", "image/png"),
            ("unsafe.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml"),
        ]
        for name, content, mime_type in samples:
            with self.subTest(filename=name):
                attachment, _ = self._upload_attachment(name, content, mime_type, "other")
                response = self.client.get(f"/api/attachment/{attachment.public_id}/file/")
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/octet-stream")
                self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(b"".join(response.streaming_content), content)

    def test_pdf_receipt_is_served_inline_to_its_owner(self):
        content = b"%PDF-1.4\nsynthetic receipt\n%%EOF"
        attachment, _ = self._upload_attachment("receipt.pdf", content, "application/pdf", "receipt")
        response = self.client.get(f"/api/attachment/{attachment.public_id}/file/")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertEqual(b"".join(response.streaming_content), content)

    def test_debug_media_urls_do_not_bypass_attachment_authentication(self):
        attachment, _ = self._upload_attachment()
        raw_url = attachment.file.url
        urlconf = importlib.import_module(settings.ROOT_URLCONF)
        # Rebuild URL patterns with DEBUG enabled to cover the development
        # media route as well as the normal test runner's DEBUG=False setting.
        try:
            with override_settings(DEBUG=True):
                importlib.reload(urlconf)
                clear_url_caches()
                self.assertEqual(Client().get(raw_url).status_code, 404)
                self.assertEqual(self.client.get(raw_url).status_code, 404)
        finally:
            importlib.reload(urlconf)
            clear_url_caches()
