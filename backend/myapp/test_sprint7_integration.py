"""Sprint 7 release acceptance, using session-authenticated, CSRF-checked APIs.

These workflows create their own inventories/categories/locations/items through
public endpoints. They require a freshly migrated test database and no eBay
credentials or network calls. Existing regression suites cover earlier sprints.
"""

import csv
import json
from io import StringIO

from django.test import TestCase

from myapp.test_integration import FrontendClient, valid_item


class Sprint7LocationWorkflowTests(TestCase):
    def setUp(self):
        self.frontend = FrontendClient()
        self.assertEqual(self.frontend.register("sprint7-owner").status_code, 201)
        self.inventory_id = self.frontend.get("/api/dashboard/").json()["inventory_id"]
        response = self.frontend.post_json(
            f"/api/inventory/{self.inventory_id}/categories/", {"name": "Electronics"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.category_public_id = response.json()["category"]["public_id"]
        self.add_url = f"/api/inventory/{self.inventory_id}/add-item/"
        self.category_id = self.frontend.get(self.add_url).json()["categories"][0]["id"]

    def location(self, name, parent=None, inventory_id=None):
        payload = {"name": name}
        if parent is not None:
            payload["parent_id"] = parent["public_id"]
        response = self.frontend.post_json(
            f"/api/inventory/{inventory_id or self.inventory_id}/locations/", payload,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["location"]

    def mutate_location(self, method, location, payload=None):
        return getattr(self.frontend.client, method)(
            f"/api/location/{location['public_id']}/",
            data=json.dumps(payload or {}), content_type="application/json",
            **self.frontend.csrf_headers(),
        )

    def test_create_assign_rename_move_filter_export_and_archive_locations(self):
        home = self.location("Home")
        basement = self.location("Basement", home)
        closet = self.location("Bedroom Closet", home)
        self.assertEqual(basement["path"], "Home → Basement")
        response = self.frontend.post_form(
            self.add_url, valid_item(self.category_id, location=basement["public_id"]),
        )
        self.assertEqual(response.status_code, 200, response.content)
        item_id = response.json()["item_id"]
        edit_url = f"/api/item/{item_id}/edit/"
        detail_url = f"/api/item/{item_id}/"

        # Item Details and the inventory filter read the same stored assignment.
        detail = self.frontend.get(detail_url).json()["item"]
        self.assertEqual(detail["location"], "Home → Basement")
        for url in (f"/api/inventory/{self.inventory_id}/", "/api/items/"):
            response = self.frontend.get(f"{url}?location={basement['public_id']}")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual([row["public_id"] for row in response.json()["items"]], [item_id])

        response = self.mutate_location("patch", home, {"name": "Main Home"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.frontend.get(detail_url).json()["item"]["location"], "Main Home → Basement")
        response = self.frontend.post_form(
            edit_url, valid_item(self.category_id, location=closet["public_id"]),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.frontend.get(detail_url).json()["item"]["location"], "Main Home → Bedroom Closet")
        self.assertEqual(self.frontend.get(f"/api/items/?location={basement['public_id']}").json()["items"], [])

        response = self.mutate_location("patch", closet, {"name": "Upper Closet"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.frontend.get(detail_url).json()["item"]["location"], "Main Home → Upper Closet")

        # The current CSV and PDF integrations still work with located items.
        response = self.frontend.get("/api/reports/csv/?purchase_prices=1&current_values=1")
        self.assertEqual(response.status_code, 200, response.content)
        rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 1)
        self.assertIn("Laptop", rows[0].values())
        self.assertIn("Upper Closet", rows[0].values())
        response = self.frontend.get("/api/reports/pdf/?purchase_prices=1&current_values=1")
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

        # An occupied location is protected; move its item before archiving it.
        self.assertEqual(self.mutate_location("delete", closet).status_code, 400)
        response = self.frontend.post_form(edit_url, valid_item(self.category_id, location=""))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.frontend.get("/api/items/?location=unassigned").json()["items"][0]["public_id"], item_id)
        self.assertEqual(self.mutate_location("delete", closet).status_code, 200)
        self.assertEqual(self.mutate_location("delete", basement).status_code, 200)
        self.assertEqual(self.mutate_location("delete", home).status_code, 200)
        self.assertEqual(self.frontend.get(self.add_url).json()["locations"], [])
        self.assertIsNone(self.frontend.get(detail_url).json()["item"]["location"])

    def test_location_scope_survives_inventory_switch_and_a_second_user(self):
        room = self.location("Basement")
        response = self.frontend.post_json("/api/inventories/", {"name": "Storage inventory"})
        self.assertEqual(response.status_code, 201, response.content)
        other_id = response.json()["inventory"]["public_id"]
        shelf = self.location("Shelf 2", inventory_id=other_id)

        # Even another inventory owned by this user cannot supply an assignment.
        response = self.frontend.post_form(
            self.add_url, valid_item(self.category_id, location=shelf["public_id"]),
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("location", response.json()["errors"])
        response = self.frontend.post_json("/api/inventories/select/", {"inventory_id": self.inventory_id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.frontend.get("/api/items/").json()["items"], [])
        response = self.frontend.get(f"/api/items/?location={shelf['public_id']}")
        self.assertEqual(response.status_code, 400, response.content)

        response = self.frontend.post_form(
            self.add_url, valid_item(self.category_id, location=room["public_id"]),
        )
        self.assertEqual(response.status_code, 200, response.content)
        item_id = response.json()["item_id"]
        response = self.frontend.post_form(
            f"/api/item/{item_id}/edit/", valid_item(self.category_id, location=shelf["public_id"]),
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.frontend.get(f"/api/item/{item_id}/").json()["item"]["location_id"], room["public_id"])

        # Exporting after a switch must not leak items or category filters from
        # the previous inventory, even though the current user owns both.
        self.assertEqual(self.frontend.post_json(
            "/api/inventories/select/", {"inventory_id": other_id},
        ).status_code, 200)
        response = self.frontend.get("/api/reports/csv/?current_values=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(csv.DictReader(StringIO(response.content.decode("utf-8-sig")))), [])
        response = self.frontend.get("/api/reports/pdf/?current_values=1")
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertTrue(response.content.startswith(b"%PDF-"))
        for report in ("csv", "pdf"):
            response = self.frontend.get(f"/api/reports/{report}/?category={self.category_public_id}")
            self.assertEqual(response.status_code, 404, response.content)

        intruder = FrontendClient()
        self.assertEqual(intruder.register("sprint7-intruder").status_code, 201)
        response = intruder.get(f"/api/inventory/{self.inventory_id}/locations/")
        self.assertEqual(response.status_code, 404, response.content)
        response = intruder.post_json(
            f"/api/inventory/{self.inventory_id}/locations/", {"name": "Unauthorized room"},
        )
        self.assertEqual(response.status_code, 404, response.content)
        response = intruder.client.patch(
            f"/api/location/{room['public_id']}/", data=json.dumps({"name": "Unauthorized rename"}),
            content_type="application/json", **intruder.csrf_headers(),
        )
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(self.frontend.get(f"/api/item/{item_id}/").json()["item"]["location"], "Basement")
