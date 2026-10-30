"""
Sprint 4 integration and regression pass.

Register -> Login -> Create/Switch Inventory -> Add Item -> Upload Attachment
-> View Item -> Edit Item -> Run Valuation -> Accept Valuation -> View History
-> Archive Item

Requests go through FrontendClient (session cookie, CSRF header, form-encoded
items), the same way the NiceGUI frontend calls the API. eBay is never called:
only its HTTP layer is replaced, so the real search_ebay() parsing and the
estimate() pipeline still run against the recorded listings fixture.

There is no valuation history endpoint yet, so "View History" is checked
against the stored ValuationRun rows.
"""

import json
import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from inventory_manager.pipeline import ebay_client
from myapp.models import Attachment, Category, Inventory, Item, ValuationRun
from myapp.test_integration import FrontendClient, valid_item


User = get_user_model()

EBAY_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "inventory_manager" / "fixtures" / "raw" / "ebay_iphone13.json"
)
EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# Result of estimate() on the recorded fixture for a used item.
FIXTURE_ESTIMATE = 247.0


def ebay_response(payload=None, status=200, body=None):
    """A real requests.Response, so raise_for_status() and json() behave like eBay's."""
    response = requests.Response()
    response.status_code = status
    response.url = EBAY_SEARCH_URL
    response._content = body if body is not None else json.dumps(payload).encode()
    return response


def fixture_payload():
    return json.loads(EBAY_FIXTURE.read_text())


@contextmanager
def fake_ebay(response=None, error=None):
    """Replace eBay's token and search HTTP calls. Yields the search mock."""
    with patch.object(ebay_client, "get_ebay_access_token", return_value="test-token"), \
            patch.object(ebay_client.requests, "get") as search:
        if error is not None:
            search.side_effect = error
        else:
            # Not `response or ...`: a Response with an error status is falsy.
            search.return_value = (
                response if response is not None else ebay_response(fixture_payload())
            )
        yield search


def phone_item(category_id, **overrides):
    return valid_item(
        category_id,
        **{
            "name": "iPhone 13",
            "brand": "Apple",
            "model_number": "128GB",
            "serial_number": "",
            "purchase_amount": "799.00",
            "description": "",
            **overrides,
        },
    )


def photo(name="phone.jpg"):
    return SimpleUploadedFile(name, b"\xff\xd8\xff fake jpeg", content_type="image/jpeg")


def receipt(name="receipt.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake", content_type="application/pdf")


class TemporaryMediaMixin:
    """Keep uploaded attachments out of backend/media."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix="coverworth-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)


class Sprint4Client(FrontendClient):
    """FrontendClient plus the Sprint 4 calls."""

    def delete(self, path):
        return self.client.delete(path, **self.csrf_headers())

    def create_inventory(self, name):
        return self.post_json("/api/inventories/", {"name": name})

    def select_inventory(self, inventory_id):
        return self.post_json("/api/inventories/select/", {"inventory_id": str(inventory_id)})

    def active_inventory_id(self):
        return self.get("/api/dashboard/").json()["inventory_id"]

    def create_category(self, inventory_id, name):
        response = self.post_json(f"/api/inventory/{inventory_id}/categories/", {"name": name})
        return Category.objects.get(public_id=response.json()["category"]["public_id"])

    def add_item(self, inventory_id, payload):
        return self.post_form(f"/api/inventory/{inventory_id}/add-item/", payload)

    def upload(self, item_id, file, file_type="photo"):
        return self.post_form(
            f"/api/item/{item_id}/attachments/",
            {"file": file, "file_type": file_type},
        )

    def run_valuation(self, item_id):
        return self.client.post(f"/api/item/{item_id}/valuation/", **self.csrf_headers())

    def accept_valuation(self, item_id, valuation_run_id):
        return self.post_json(
            f"/api/item/{item_id}/valuation/accept/",
            {"valuation_run_id": valuation_run_id},
        )

    def archive_item(self, item_id):
        return self.delete(f"/api/item/{item_id}/edit/")


class Sprint4WorkflowTestCase(TemporaryMediaMixin, TestCase):
    def test_primary_workflow_from_register_to_archive(self):
        frontend = Sprint4Client()

        # Register, then Login again in a fresh session
        self.assertEqual(frontend.register("alice").status_code, 201)
        frontend.logout()
        self.assertEqual(frontend.get("/api/dashboard/").status_code, 401)
        self.assertEqual(frontend.login("alice").status_code, 200)
        default_inventory = frontend.active_inventory_id()

        # Create Inventory: the new one becomes active
        response = frontend.create_inventory("Garage")
        self.assertEqual(response.status_code, 201, response.content)
        garage = response.json()["inventory"]["public_id"]
        self.assertEqual(frontend.active_inventory_id(), garage)

        listing = frontend.get("/api/inventories/").json()
        self.assertEqual(
            [inv["name"] for inv in listing["inventories"]],
            ["My Inventory", "Garage"],
        )
        self.assertEqual(listing["active_inventory_id"], garage)

        # Switch Inventory away and back
        self.assertEqual(frontend.select_inventory(default_inventory).status_code, 200)
        self.assertEqual(frontend.active_inventory_id(), default_inventory)
        self.assertEqual(frontend.select_inventory(garage).status_code, 200)
        self.assertEqual(frontend.active_inventory_id(), garage)

        # Add Item
        category = frontend.create_category(garage, "Phones")
        response = frontend.add_item(garage, phone_item(category.id))
        self.assertEqual(response.status_code, 200, response.content)
        item_id = response.json()["item_id"]

        # Upload Attachment: the first photo becomes primary, a receipt never does
        response = frontend.upload(item_id, photo())
        self.assertEqual(response.status_code, 201, response.content)
        photo_url = response.json()["attachment"]["file_url"]
        self.assertEqual(frontend.upload(item_id, receipt(), "receipt").status_code, 201)

        attachments = frontend.get(f"/api/item/{item_id}/attachments/").json()["attachments"]
        self.assertEqual(
            sorted((a["original_filename"], a["file_type"], a["is_primary"]) for a in attachments),
            [("phone.jpg", "photo", True), ("receipt.pdf", "receipt", False)],
        )

        # View Item
        detail = frontend.get(f"/api/item/{item_id}/").json()
        self.assertEqual(detail["item"]["name"], "iPhone 13")
        self.assertEqual(detail["item"]["category"], "Phones")
        self.assertEqual(detail["inventory"], {"public_id": garage, "name": "Garage"})
        self.assertIsNone(detail["item"]["current_estimated_amount"])
        self.assertIsNone(detail["item"]["valuation_date"])

        inventory = frontend.get(f"/api/inventory/{garage}/").json()
        self.assertEqual(inventory["items"][0]["primary_photo_url"], photo_url)

        # The item belongs to Garage only
        self.assertEqual(frontend.get(f"/api/inventory/{default_inventory}/").json()["items"], [])

        # Edit Item
        response = frontend.post_form(
            f"/api/item/{item_id}/edit/",
            phone_item(category.id, notes="Cracked corner"),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(frontend.get(f"/api/item/{item_id}/").json()["item"]["notes"], "Cracked corner")

        # Run Valuation
        with fake_ebay() as search:
            response = frontend.run_valuation(item_id)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(search.call_args.kwargs["params"]["q"], "iPhone 13 Apple 128GB")
        valuation = response.json()
        self.assertEqual(valuation["estimate"], FIXTURE_ESTIMATE)
        self.assertEqual(valuation["sample_count"], 11)
        self.assertEqual(valuation["confidence"], "medium")
        self.assertIsNotNone(valuation["valuation_run_id"])

        # Running a valuation does not change the item until it is accepted
        self.assertIsNone(Item.objects.get(public_id=item_id).current_estimated_amount)

        # Accept Valuation
        response = frontend.accept_valuation(item_id, valuation["valuation_run_id"])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["estimated_value"], FIXTURE_ESTIMATE)

        detail = frontend.get(f"/api/item/{item_id}/").json()["item"]
        self.assertEqual(detail["current_estimated_amount"], "247.00")
        self.assertIsNotNone(detail["valuation_date"])

        # View History: stored on the item (no history endpoint yet)
        runs = ValuationRun.objects.filter(item__public_id=item_id)
        self.assertEqual(
            [(run.status, run.estimated_amount, run.requested_by.username) for run in runs],
            [("success", Decimal("247.00"), "alice")],
        )
        self.assertEqual(runs[0].input_snapshot["query"], "iPhone 13 Apple 128GB")

        # Archive Item
        response = frontend.archive_item(item_id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["success"])

        self.assertEqual(frontend.get("/api/items/").json()["items"], [])
        self.assertEqual(frontend.get(f"/api/inventory/{garage}/").json()["items"], [])
        self.assertEqual(frontend.get("/api/dashboard/").json()["summary"]["total_items"], 0)
        self.assertEqual(frontend.get(f"/api/item/{item_id}/").status_code, 404)

        # Archiving keeps the record and its history
        item = Item.objects.get(public_id=item_id)
        self.assertIsNotNone(item.archived_at)
        self.assertEqual(item.valuation_runs.count(), 1)
        self.assertEqual(item.attachments.count(), 2)

    def test_accepted_valuation_becomes_the_displayed_value(self):
        """Explicit acceptance changes the value shown by item and dashboard reads."""
        frontend = Sprint4Client()
        frontend.register("alice")
        inventory_id = frontend.active_inventory_id()
        category = frontend.create_category(inventory_id, "Phones")
        item_id = frontend.add_item(inventory_id, phone_item(category.id)).json()["item_id"]

        with fake_ebay():
            run_id = frontend.run_valuation(item_id).json()["valuation_run_id"]
        frontend.accept_valuation(item_id, run_id)

        detail = frontend.get(f"/api/item/{item_id}/").json()["item"]
        self.assertEqual(detail["effective_value"], "247.00")
        self.assertEqual(detail["effective_value_source"], "estimated")
        self.assertIsNone(detail["manual_value"])
        self.assertEqual(frontend.get("/api/dashboard/").json()["summary"]["estimated_value"], 247.0)


class UserIsolationTestCase(TemporaryMediaMixin, TestCase):
    """A second user cannot see or change anything in the first user's inventories."""

    def setUp(self):
        self.owner = Sprint4Client()
        self.owner.register("alice")
        self.inventory_id = self.owner.active_inventory_id()
        self.category = self.owner.create_category(self.inventory_id, "Phones")
        self.item_id = self.owner.add_item(
            self.inventory_id, phone_item(self.category.id)
        ).json()["item_id"]
        self.attachment_id = self.owner.upload(self.item_id, photo()).json()["attachment"]["public_id"]
        with fake_ebay():
            self.run_id = self.owner.run_valuation(self.item_id).json()["valuation_run_id"]

        self.intruder = Sprint4Client()
        self.intruder.register("mallory")

    def assertDenied(self, response):
        self.assertIn(response.status_code, (403, 404), response.content)

    def test_other_user_cannot_see_or_select_the_inventory(self):
        listing = self.intruder.get("/api/inventories/").json()
        self.assertNotIn(
            self.inventory_id,
            [inv["public_id"] for inv in listing["inventories"]],
        )

        self.assertEqual(self.intruder.select_inventory(self.inventory_id).status_code, 404)
        self.assertNotEqual(self.intruder.active_inventory_id(), self.inventory_id)
        self.assertEqual(self.intruder.get("/api/items/").json()["items"], [])

        for path in [
            f"/api/inventory/{self.inventory_id}/",
            f"/api/inventory/{self.inventory_id}/add-item/",
            f"/api/inventory/{self.inventory_id}/categories/",
        ]:
            with self.subTest(path):
                self.assertDenied(self.intruder.get(path))

    def test_other_user_cannot_add_to_the_inventory(self):
        self.assertDenied(self.intruder.add_item(self.inventory_id, phone_item(self.category.id)))
        self.assertDenied(self.intruder.post_json(
            f"/api/inventory/{self.inventory_id}/categories/", {"name": "Mine now"}
        ))

        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)

    def test_other_user_cannot_read_the_item(self):
        for path in [
            f"/api/item/{self.item_id}/",
            f"/api/item/{self.item_id}/edit/",
            f"/api/item/{self.item_id}/attachments/",
        ]:
            with self.subTest(path):
                self.assertDenied(self.intruder.get(path))

    def test_other_user_cannot_change_the_item(self):
        responses = {
            "edit": self.intruder.post_form(
                f"/api/item/{self.item_id}/edit/", phone_item(self.category.id, name="Stolen")
            ),
            "archive": self.intruder.archive_item(self.item_id),
            "upload": self.intruder.upload(self.item_id, photo("theirs.jpg")),
            "delete attachment": self.intruder.delete(f"/api/attachment/{self.attachment_id}/"),
            "accept valuation": self.intruder.accept_valuation(self.item_id, self.run_id),
        }
        with fake_ebay() as search:
            responses["run valuation"] = self.intruder.run_valuation(self.item_id)

        for label, response in responses.items():
            with self.subTest(label):
                self.assertDenied(response)

        search.assert_not_called()
        item = Item.objects.get(public_id=self.item_id)
        self.assertEqual(item.name, "iPhone 13")
        self.assertIsNone(item.archived_at)
        self.assertIsNone(item.current_estimated_amount)
        self.assertEqual(
            list(item.attachments.values_list("original_filename", "archived_at")),
            [("phone.jpg", None)],
        )
        self.assertEqual(item.valuation_runs.count(), 1)

    def test_anonymous_requests_to_sprint4_endpoints_are_rejected(self):
        anonymous = Client()
        cases = [
            ("get", "/api/inventories/"),
            ("post", "/api/inventories/"),
            ("post", "/api/inventories/select/"),
            ("get", f"/api/item/{self.item_id}/attachments/"),
            ("post", f"/api/item/{self.item_id}/attachments/"),
            ("delete", f"/api/attachment/{self.attachment_id}/"),
            ("delete", f"/api/item/{self.item_id}/edit/"),
            ("post", f"/api/item/{self.item_id}/valuation/"),
            ("post", f"/api/item/{self.item_id}/valuation/accept/"),
        ]
        for method, path in cases:
            with self.subTest(f"{method.upper()} {path}"):
                self.assertEqual(getattr(anonymous, method)(path).status_code, 401)


class EmptyInventoryTestCase(TemporaryMediaMixin, TestCase):
    def setUp(self):
        self.frontend = Sprint4Client()
        self.frontend.register("alice")

    def assertInventoryIsEmpty(self, inventory_id):
        self.assertEqual(self.frontend.active_inventory_id(), inventory_id)

        dashboard = self.frontend.get("/api/dashboard/").json()
        self.assertEqual(
            dashboard["summary"],
            {
                "total_items": 0,
                "estimated_value": 0.0,
                "purchase_value": 0.0,
                "items_needing_attention": 0,
            },
        )
        self.assertEqual(dashboard["category_data"], [])
        self.assertEqual(dashboard["recent_items"], [])
        self.assertEqual(self.frontend.get("/api/items/").json(), {"items": []})
        self.assertEqual(self.frontend.get(f"/api/inventory/{inventory_id}/").json()["items"], [])

    def test_new_inventory_starts_empty_even_when_another_has_items(self):
        default_inventory = self.frontend.active_inventory_id()
        category = self.frontend.create_category(default_inventory, "Phones")
        self.frontend.add_item(default_inventory, phone_item(category.id))

        empty = self.frontend.create_inventory("Storage Unit").json()["inventory"]["public_id"]

        self.assertInventoryIsEmpty(empty)
        self.assertEqual(
            self.frontend.get(f"/api/inventory/{empty}/categories/").json()["categories"],
            [],
        )
        self.assertEqual(
            self.frontend.get(f"/api/inventory/{empty}/add-item/").json()["categories"],
            [],
        )
        counts = {
            inv["name"]: inv["item_count"]
            for inv in self.frontend.get("/api/inventories/").json()["inventories"]
        }
        self.assertEqual(counts, {"My Inventory": 1, "Storage Unit": 0})

    def test_archiving_the_last_item_empties_the_inventory(self):
        inventory_id = self.frontend.active_inventory_id()
        category = self.frontend.create_category(inventory_id, "Phones")
        item_id = self.frontend.add_item(inventory_id, phone_item(category.id)).json()["item_id"]

        self.frontend.archive_item(item_id)

        self.assertInventoryIsEmpty(inventory_id)
        self.assertEqual(
            self.frontend.get(f"/api/inventory/{inventory_id}/categories/").json()["categories"][0]["item_count"],
            0,
        )

    def test_duplicate_inventory_name_is_rejected(self):
        response = self.frontend.create_inventory("my inventory")

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])
        self.assertEqual(Inventory.objects.count(), 1)


class InvalidIdTestCase(TemporaryMediaMixin, TestCase):
    def setUp(self):
        self.frontend = Sprint4Client()
        self.frontend.register("alice")
        inventory_id = self.frontend.active_inventory_id()
        self.category = self.frontend.create_category(inventory_id, "Phones")
        self.item_id = self.frontend.add_item(
            inventory_id, phone_item(self.category.id)
        ).json()["item_id"]
        self.missing = uuid.uuid4()

    def test_missing_ids_return_json_404(self):
        cases = {
            "archive item": lambda: self.frontend.archive_item(self.missing),
            "list attachments": lambda: self.frontend.get(f"/api/item/{self.missing}/attachments/"),
            "upload attachment": lambda: self.frontend.upload(self.missing, photo()),
            "delete attachment": lambda: self.frontend.delete(f"/api/attachment/{self.missing}/"),
            "run valuation": lambda: self.frontend.run_valuation(self.missing),
            "accept valuation": lambda: self.frontend.accept_valuation(self.missing, str(uuid.uuid4())),
        }
        for label, request in cases.items():
            with self.subTest(label):
                response = request()

                self.assertEqual(response.status_code, 404, response.content)
                self.assertIn("error", response.json())

    def test_malformed_ids_do_not_match_any_route(self):
        for path in [
            "/api/item/not-a-uuid/attachments/",
            "/api/item/not-a-uuid/valuation/",
            "/api/attachment/123/",
            "/api/inventory/None/",
        ]:
            with self.subTest(path):
                self.assertEqual(self.frontend.get(path).status_code, 404)

    def test_accept_rejects_bad_valuation_run_ids(self):
        with fake_ebay():
            other_item = self.frontend.add_item(
                self.frontend.active_inventory_id(), phone_item(self.category.id, name="iPhone 13 spare")
            ).json()["item_id"]
            other_run = self.frontend.run_valuation(other_item).json()["valuation_run_id"]

        failed_run = ValuationRun.objects.create(
            item=Item.objects.get(public_id=self.item_id),
            status="failed",
        )
        cases = {
            "missing": ({}, 400),
            "empty": ({"valuation_run_id": ""}, 400),
            "malformed": ({"valuation_run_id": "not-a-uuid"}, 400),
            "unknown": ({"valuation_run_id": str(uuid.uuid4())}, 404),
            "belongs to another item": ({"valuation_run_id": other_run}, 404),
            "did not succeed": ({"valuation_run_id": str(failed_run.public_id)}, 404),
        }
        for label, (payload, status) in cases.items():
            with self.subTest(label):
                response = self.frontend.post_json(
                    f"/api/item/{self.item_id}/valuation/accept/", payload
                )

                self.assertEqual(response.status_code, status, response.content)
                self.assertIn("error", response.json())

        self.assertIsNone(Item.objects.get(public_id=self.item_id).current_estimated_amount)

    def test_accept_rejects_invalid_json(self):
        response = self.frontend.client.post(
            f"/api/item/{self.item_id}/valuation/accept/",
            data="{not json",
            content_type="application/json",
            **self.frontend.csrf_headers(),
        )

        self.assertEqual(response.status_code, 400)

    def test_archived_item_is_treated_as_missing(self):
        attachment_id = self.frontend.upload(self.item_id, photo()).json()["attachment"]["public_id"]
        self.assertEqual(self.frontend.archive_item(self.item_id).status_code, 200)

        cases = {
            "view": lambda: self.frontend.get(f"/api/item/{self.item_id}/"),
            "edit form": lambda: self.frontend.get(f"/api/item/{self.item_id}/edit/"),
            "edit": lambda: self.frontend.post_form(
                f"/api/item/{self.item_id}/edit/", phone_item(self.category.id, name="Revived")
            ),
            "archive again": lambda: self.frontend.archive_item(self.item_id),
            "list attachments": lambda: self.frontend.get(f"/api/item/{self.item_id}/attachments/"),
            "upload attachment": lambda: self.frontend.upload(self.item_id, photo("late.jpg")),
            "run valuation": lambda: self.frontend.run_valuation(self.item_id),
        }
        with fake_ebay() as search:
            for label, request in cases.items():
                with self.subTest(label):
                    self.assertEqual(request().status_code, 404)

        search.assert_not_called()
        item = Item.objects.get(public_id=self.item_id)
        self.assertEqual(item.name, "iPhone 13")
        self.assertEqual(item.attachments.count(), 1)
        self.assertTrue(Attachment.objects.filter(public_id=attachment_id).exists())

    def test_attachment_upload_errors(self):
        no_file = self.frontend.post_form(
            f"/api/item/{self.item_id}/attachments/", {"file_type": "photo"}
        )
        self.assertEqual(no_file.status_code, 400)
        self.assertEqual(no_file.json()["error"], "No file uploaded.")

        bad_type = self.frontend.upload(self.item_id, photo(), file_type="virus")
        self.assertEqual(bad_type.status_code, 400)
        self.assertEqual(bad_type.json()["error"], "Invalid file type.")

        self.assertFalse(Attachment.objects.exists())

    def test_deleted_attachment_cannot_be_deleted_again(self):
        attachment_id = self.frontend.upload(self.item_id, photo()).json()["attachment"]["public_id"]

        self.assertEqual(self.frontend.delete(f"/api/attachment/{attachment_id}/").status_code, 200)
        self.assertEqual(self.frontend.delete(f"/api/attachment/{attachment_id}/").status_code, 404)
        self.assertEqual(
            self.frontend.get(f"/api/item/{self.item_id}/attachments/").json()["attachments"],
            [],
        )


class EbayFailureTestCase(TestCase):
    """eBay problems come back as a JSON 502 the frontend can show, never a crash."""

    def setUp(self):
        self.frontend = Sprint4Client()
        self.frontend.register("alice")
        inventory_id = self.frontend.active_inventory_id()
        category = self.frontend.create_category(inventory_id, "Phones")
        self.item_id = self.frontend.add_item(
            inventory_id, phone_item(category.id)
        ).json()["item_id"]

    def assertUsefulEbayError(self, response):
        self.assertEqual(response.status_code, 502, response.content)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"error": "Unable to retrieve eBay listings"})
        self.assertFalse(ValuationRun.objects.exists())
        self.assertIsNone(Item.objects.get(public_id=self.item_id).current_estimated_amount)

    def test_eBay_request_failures(self):
        cases = {
            "server error": {"response": ebay_response({"errors": []}, status=500)},
            "rate limited": {"response": ebay_response({"errors": []}, status=429)},
            "expired token": {"response": ebay_response({"errors": []}, status=401)},
            "timeout": {"error": requests.Timeout("read timed out")},
            "network down": {"error": requests.ConnectionError("no route to host")},
            "html instead of json": {"response": ebay_response(body=b"<html>Service Unavailable</html>")},
            "listing without a title": {"response": ebay_response({
                "itemSummaries": [{
                    "price": {"value": "250.00", "currency": "USD"},
                    "buyingOptions": ["FIXED_PRICE"],
                }],
            })},
        }
        for label, fake in cases.items():
            with self.subTest(label):
                with fake_ebay(**fake) as search:
                    response = self.frontend.run_valuation(self.item_id)

                search.assert_called_once()
                self.assertUsefulEbayError(response)

    def test_missing_eBay_credentials(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("EBAY_")}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(ebay_client, "_cached_token", None), \
                patch.object(ebay_client.requests, "post") as token_request, \
                patch.object(ebay_client.requests, "get") as search:
            response = self.frontend.run_valuation(self.item_id)

        token_request.assert_not_called()
        search.assert_not_called()
        self.assertUsefulEbayError(response)

    def test_too_few_comparable_listings(self):
        with fake_ebay(ebay_response({"itemSummaries": []})):
            response = self.frontend.run_valuation(self.item_id)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["estimate"])
        self.assertEqual(data["confidence"], "insufficient")
        self.assertEqual(data["sample_count"], 0)
        self.assertIsNone(data["valuation_run_id"])
        self.assertFalse(ValuationRun.objects.exists())

    def test_non_usd_and_auction_listings_are_ignored(self):
        payload = fixture_payload()
        for summary in payload["itemSummaries"]:
            summary["price"]["currency"] = "GBP"

        with fake_ebay(ebay_response(payload)):
            response = self.frontend.run_valuation(self.item_id)

        self.assertEqual(response.json()["sample_count"], 0)
        self.assertIsNone(response.json()["estimate"])

    def test_new_condition_items_are_valued_against_new_listings(self):
        item = Item.objects.get(public_id=self.item_id)
        item.condition = "new"
        item.save()

        with fake_ebay():
            response = self.frontend.run_valuation(self.item_id)

        data = response.json()
        self.assertEqual((data["estimate"], data["sample_count"]), (229.99, 3))
        self.assertEqual(
            ValuationRun.objects.get(public_id=data["valuation_run_id"]).input_snapshot["condition"],
            "new",
        )

    def test_valuation_requires_post(self):
        with fake_ebay() as search:
            response = self.frontend.get(f"/api/item/{self.item_id}/valuation/")

        self.assertEqual(response.status_code, 405)
        search.assert_not_called()
