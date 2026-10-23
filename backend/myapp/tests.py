import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone

from myapp.models import Attachment, Category, Inventory, Item
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