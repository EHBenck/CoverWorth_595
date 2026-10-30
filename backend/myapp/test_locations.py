"""Regression coverage for inventory-scoped locations and item assignments."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone

from myapp.forms import ItemForm
from myapp.models import Category, Inventory, Item, Location


class LocationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="location-owner")
        cls.stranger = User.objects.create_user(username="location-stranger")
        cls.inventory = Inventory.objects.create(owner=cls.owner, name="Main")
        cls.other_inventory = Inventory.objects.create(owner=cls.owner, name="Second")
        cls.foreign_inventory = Inventory.objects.create(owner=cls.stranger, name="Private")
        cls.category = Category.objects.create(inventory=cls.inventory, name="Electronics")
        cls.home = Location.objects.create(inventory=cls.inventory, name="Home")
        cls.basement = Location.objects.create(inventory=cls.inventory, name="Basement", parent=cls.home)
        cls.office = Location.objects.create(inventory=cls.inventory, name="Office", parent=cls.home)
        cls.other_location = Location.objects.create(inventory=cls.other_inventory, name="Other room")
        cls.foreign_location = Location.objects.create(inventory=cls.foreign_inventory, name="Private room")
        cls.archived_location = Location.objects.create(
            inventory=cls.inventory, name="Archived room", archived_at=timezone.now(),
        )
        cls.item = Item.objects.create(
            inventory=cls.inventory, category=cls.category, name="Laptop",
            location=cls.basement, purchase_date="2026-01-15", purchase_amount="100.00",
        )
        cls.unassigned_item = Item.objects.create(inventory=cls.inventory, name="Unassigned item")

    def setUp(self):
        self.client.force_login(self.owner)
        self.collection_url = f"/api/inventory/{self.inventory.public_id}/locations/"
        self.add_url = f"/api/inventory/{self.inventory.public_id}/add-item/"
        self.edit_url = f"/api/item/{self.item.public_id}/edit/"

    def location_url(self, location):
        return f"/api/location/{location.public_id}/"

    def create_location(self, payload, inventory=None):
        inventory = inventory or self.inventory
        return self.client.post(
            f"/api/inventory/{inventory.public_id}/locations/",
            json.dumps(payload), content_type="application/json",
        )

    def patch_location(self, location, payload):
        return self.client.patch(
            self.location_url(location), json.dumps(payload), content_type="application/json",
        )

    def item_data(self, **overrides):
        data = {
            "name": "Laptop", "category": str(self.category.pk),
            "purchase_date": "2026-01-15", "purchase_amount": "100.00",
            "condition": "used", "quantity": "1",
        }
        data.update(overrides)
        return data

    def assert_invalid(self, response, field=None):
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(response.json()["success"])
        if field is not None:
            self.assertIn(field, response.json()["errors"])

    def test_location_and_item_endpoints_require_authentication(self):
        self.client.logout()
        for method, url, data in [
            ("get", self.collection_url, None),
            ("post", self.collection_url, {"name": "Garage"}),
            ("patch", self.location_url(self.home), {"name": "Changed"}),
            ("delete", self.location_url(self.office), None),
            ("get", self.add_url, None),
            ("get", self.edit_url, None),
        ]:
            with self.subTest(method=method, url=url):
                kwargs = {"data": json.dumps(data), "content_type": "application/json"} if data is not None else {}
                self.assertEqual(getattr(self.client, method)(url, **kwargs).status_code, 401)

    def test_location_mutations_keep_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for method, url in [
            ("post", self.collection_url),
            ("patch", self.location_url(self.home)),
            ("delete", self.location_url(self.office)),
        ]:
            with self.subTest(method=method):
                response = getattr(client, method)(url, data='{"name":"Room"}', content_type="application/json")
                self.assertEqual(response.status_code, 403)
        csrf = client.get("/api/auth/csrf/").cookies["csrftoken"].value
        response = client.post(
            self.collection_url, data='{"name":"Garage"}', content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_create_list_trim_fields_and_expose_uuid_hierarchy(self):
        response = self.create_location({
            "name": "  Storage  ", "description": "  Holiday decorations  ",
            "parent_id": str(self.basement.public_id),
        })
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()["location"]
        self.assertEqual(payload["name"], "Storage")
        self.assertEqual(payload["description"], "Holiday decorations")
        self.assertEqual(payload["parent_id"], str(self.basement.public_id))
        self.assertEqual(payload["path"], "Home → Basement → Storage")
        saved = Location.objects.get(public_id=payload["public_id"])
        self.assertEqual(saved.inventory, self.inventory)
        listing = self.client.get(self.collection_url).json()
        self.assertEqual(listing["inventory"]["public_id"], str(self.inventory.public_id))
        ids = {row["public_id"] for row in listing["locations"]}
        self.assertEqual(ids, {str(location.public_id) for location in [self.home, self.basement, self.office, saved]})

    def test_foreign_and_archived_inventory_locations_are_inaccessible(self):
        archived = Inventory.objects.create(owner=self.owner, name="Old", archived_at=timezone.now())
        archived_child = Location.objects.create(inventory=archived, name="Room")
        for inventory, location in [(self.foreign_inventory, self.foreign_location), (archived, archived_child)]:
            with self.subTest(inventory=inventory.name):
                url = f"/api/inventory/{inventory.public_id}/locations/"
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.create_location({"name": "New"}, inventory).status_code, 404)
                self.assertEqual(self.patch_location(location, {"name": "Changed"}).status_code, 404)
                self.assertEqual(self.client.delete(self.location_url(location)).status_code, 404)
                location.refresh_from_db()
                self.assertEqual(location.name, "Room" if inventory == archived else "Private room")
                self.assertIsNone(location.archived_at)

    def test_invalid_json_shapes_and_field_types_are_validation_errors(self):
        for raw in ["{", "[]", "null", '"name"', "1"]:
            with self.subTest(raw=raw):
                self.assert_invalid(self.client.post(self.collection_url, raw, content_type="application/json"))
                self.assert_invalid(self.client.patch(self.location_url(self.home), raw, content_type="application/json"))
        for payload, field in [
            ({}, "name"), ({"name": "   "}, "name"),
            ({"name": None}, "name"), ({"name": 1}, "name"),
            ({"name": []}, "name"), ({"name": "x" * 256}, "name"),
            ({"name": "New", "description": None}, "description"),
            ({"name": "New", "description": {}}, "description"),
        ]:
            with self.subTest(payload=payload):
                self.assert_invalid(self.create_location(payload), field)

    def test_parent_must_be_active_uuid_in_exact_same_inventory(self):
        for parent in [
            "bad-uuid", "", 1, True, {}, [], str(uuid4()),
            str(self.other_location.public_id), str(self.foreign_location.public_id),
            str(self.archived_location.public_id),
        ]:
            with self.subTest(parent=parent):
                self.assert_invalid(self.create_location({"name": "New", "parent_id": parent}), "parent_id")
                self.assert_invalid(self.patch_location(self.office, {"parent_id": parent}), "parent_id")
        self.office.refresh_from_db()
        self.assertEqual(self.office.parent, self.home)

    def test_immutable_and_unknown_location_fields_are_rejected(self):
        count = Location.objects.count()
        for field, value in [
            ("inventory", self.other_inventory.pk),
            ("inventory_id", str(self.other_inventory.public_id)),
            ("public_id", str(uuid4())),
            ("id", self.other_location.pk),
            ("archived_at", timezone.now().isoformat()),
            ("owner", self.stranger.pk),
            ("parent", self.home.pk),
            ("unexpected", "value"),
        ]:
            with self.subTest(field=field):
                self.assert_invalid(self.create_location({"name": "New", field: value}), field)
                self.assert_invalid(self.patch_location(self.office, {"name": "Changed", field: value}), field)
        self.office.refresh_from_db()
        self.assertEqual(self.office.name, "Office")
        self.assertEqual(self.office.inventory, self.inventory)
        self.assertEqual(self.office.parent, self.home)
        self.assertIsNone(self.office.archived_at)
        self.assertEqual(Location.objects.count(), count)

    def test_self_parent_and_multilevel_cycles_are_rejected(self):
        deep = Location.objects.create(inventory=self.inventory, name="Shelf", parent=self.basement)
        for location, parent in [(self.home, self.home), (self.home, self.basement), (self.home, deep), (self.basement, deep)]:
            with self.subTest(location=location.name, parent=parent.name):
                self.assert_invalid(self.patch_location(location, {"parent_id": str(parent.public_id)}), "parent_id")
        self.home.refresh_from_db()
        self.assertIsNone(self.home.parent)

    def test_duplicate_names_are_case_insensitive_only_within_siblings(self):
        for payload in [
            {"name": " home "},
            {"name": " BASEMENT ", "parent_id": str(self.home.public_id)},
        ]:
            self.assert_invalid(self.create_location(payload), "name")
        self.assert_invalid(self.patch_location(self.office, {"name": " basement "}), "name")
        allowed = self.create_location({"name": "Basement", "parent_id": str(self.office.public_id)})
        self.assertEqual(allowed.status_code, 201, allowed.content)
        root = self.create_location({"name": "Basement"})
        self.assertEqual(root.status_code, 201, root.content)
        self.assert_invalid(self.patch_location(self.basement, {"parent_id": None}), "name")
        other = self.create_location({"name": "Home"}, self.other_inventory)
        self.assertEqual(other.status_code, 201, other.content)

    def test_partial_rename_and_reparent_refresh_descendant_paths(self):
        self.home.description = "Keep description"
        self.home.save()
        response = self.patch_location(self.home, {"name": " Main Home "})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["location"]["description"], "Keep description")
        response = self.patch_location(self.basement, {"parent_id": str(self.office.public_id)})
        self.assertEqual(response.json()["location"]["path"], "Main Home → Office → Basement")
        response = self.patch_location(self.office, {"parent_id": None})
        self.assertIsNone(response.json()["location"]["parent_id"])
        detail = self.client.get(f"/api/item/{self.item.public_id}/").json()
        self.assertEqual(detail["item"]["location"], "Office → Basement")
        self.office.refresh_from_db()
        self.assertIsNone(self.office.parent)

    def test_archive_rejects_active_children_and_assigned_active_items(self):
        response = self.client.delete(self.location_url(self.home))
        self.assert_invalid(response)
        self.assertIn("child locations", response.json()["error"])
        response = self.client.delete(self.location_url(self.basement))
        self.assert_invalid(response)
        self.assertIn("Move or unassign", response.json()["error"])
        self.home.refresh_from_db()
        self.basement.refresh_from_db()
        self.item.refresh_from_db()
        self.assertIsNone(self.home.archived_at)
        self.assertIsNone(self.basement.archived_at)
        self.assertEqual(self.item.location, self.basement)

    def test_archive_empty_location_is_soft_and_name_can_be_reused(self):
        Location.objects.create(inventory=self.inventory, name="Old child", parent=self.office, archived_at=timezone.now())
        old_item = Item.objects.create(inventory=self.inventory, name="Old item", location=self.office, archived_at=timezone.now())
        response = self.client.delete(self.location_url(self.office))
        self.assertEqual(response.status_code, 200, response.content)
        self.office.refresh_from_db()
        self.assertIsNotNone(self.office.archived_at)
        old_item.refresh_from_db()
        self.assertEqual(old_item.location, self.office)
        ids = {row["public_id"] for row in self.client.get(self.collection_url).json()["locations"]}
        self.assertNotIn(str(self.office.public_id), ids)
        self.assertEqual(self.patch_location(self.office, {"name": "Restored"}).status_code, 404)
        self.assertEqual(self.client.delete(self.location_url(self.office)).status_code, 404)
        response = self.create_location({"name": "Office", "parent_id": str(self.home.public_id)})
        self.assertEqual(response.status_code, 201, response.content)

    def test_item_form_options_are_active_scoped_and_use_uuid_values(self):
        for url in (self.add_url, self.edit_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.content)
                rows = {row["public_id"]: row for row in response.json()["locations"]}
                self.assertEqual(set(rows), {str(loc.public_id) for loc in (self.home, self.basement, self.office)})
                self.assertEqual(rows[str(self.basement.public_id)]["path"], "Home → Basement")
        form = ItemForm(self.inventory, instance=self.item)
        self.assertEqual(form["location"].value(), str(self.basement.public_id))
        self.assertEqual(form.fields["location"].to_field_name, "public_id")
        self.assertFalse(form.fields["location"].required)
        session = self.client.session
        session["active_inventory_id"] = str(self.other_inventory.public_id)
        session.save()
        response = self.client.get(self.edit_url).json()
        self.assertEqual(response["item"]["inventory_id"], str(self.inventory.public_id))
        self.assertEqual(response["item"]["location_id"], str(self.basement.public_id))
        self.assertNotIn(str(self.other_location.public_id), {row["public_id"] for row in response["locations"]})

    def test_add_item_with_uuid_location_and_without_location(self):
        for overrides, expected in [({"location": str(self.office.public_id)}, self.office), ({}, None), ({"location": ""}, None)]:
            with self.subTest(overrides=overrides):
                response = self.client.post(self.add_url, self.item_data(**overrides))
                self.assertEqual(response.status_code, 200, response.content)
                created = Item.objects.get(public_id=response.json()["item_id"])
                self.assertEqual(created.location, expected)

    def test_item_edit_changes_location_and_omission_preserves_assignment(self):
        response = self.client.post(self.edit_url, self.item_data(location=str(self.office.public_id)))
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.post(self.edit_url, self.item_data(name="Renamed laptop"))
        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.location, self.office)
        self.assertEqual(self.item.name, "Renamed laptop")

    def test_explicit_empty_form_and_json_null_unassign_items(self):
        response = self.client.post(self.edit_url, self.item_data(location=""))
        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.location)
        self.item.location = self.basement
        self.item.save()
        response = self.client.post(self.edit_url, json.dumps(self.item_data(location=None)), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.location)
        response = self.client.delete(self.location_url(self.basement))
        self.assertEqual(response.status_code, 200, response.content)

    def test_json_item_create_and_omitted_edit_location_work(self):
        response = self.client.post(self.add_url, json.dumps(self.item_data(location=str(self.office.public_id))), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        created = Item.objects.get(public_id=response.json()["item_id"])
        self.assertEqual(created.location, self.office)
        response = self.client.post(self.edit_url, json.dumps(self.item_data(name="JSON edit")), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.location, self.basement)

    def test_invalid_item_locations_do_not_create_or_change_items(self):
        count = Item.objects.count()
        for value in [
            str(self.other_location.public_id), str(self.foreign_location.public_id),
            str(self.archived_location.public_id), str(uuid4()), "not-a-uuid", str(self.office.pk),
        ]:
            for url in (self.add_url, self.edit_url):
                with self.subTest(value=value, url=url):
                    self.assert_invalid(self.client.post(url, self.item_data(location=value)), "location")
        for value in [True, 1, [], {}]:
            for url in (self.add_url, self.edit_url):
                with self.subTest(value=value, url=url):
                    response = self.client.post(url, json.dumps(self.item_data(location=value)), content_type="application/json")
                    self.assert_invalid(response, "location")
        self.item.refresh_from_db()
        self.assertEqual(self.item.location, self.basement)
        self.assertEqual(Item.objects.count(), count)

    def test_malformed_json_item_payloads_return_validation_errors(self):
        for raw in ["{", "[]", "null"]:
            for url in (self.add_url, self.edit_url):
                with self.subTest(raw=raw, url=url):
                    self.assert_invalid(self.client.post(url, raw, content_type="application/json"))

    def test_all_item_payloads_include_location_uuid_and_full_path(self):
        responses = [
            self.client.get(f"/api/inventory/{self.inventory.public_id}/").json()["items"],
            self.client.get("/api/items/").json()["items"],
            [self.client.get(f"/api/item/{self.item.public_id}/").json()["item"]],
            [self.client.get(self.edit_url).json()["item"]],
        ]
        for rows in responses:
            row = next(row for row in rows if row["public_id"] == str(self.item.public_id))
            self.assertEqual(row["location_id"], str(self.basement.public_id))
            self.assertEqual(row["location"], "Home → Basement")
            for unassigned in [row for row in rows if row["public_id"] == str(self.unassigned_item.public_id)]:
                self.assertIsNone(unassigned["location_id"])
                self.assertIsNone(unassigned["location"])

    def test_location_filter_is_exact_scoped_and_supports_unassigned(self):
        Item.objects.create(inventory=self.other_inventory, name="Other item", location=self.other_location)
        Item.objects.create(inventory=self.inventory, name="Archived item", location=self.basement, archived_at=timezone.now())
        for url in (f"/api/inventory/{self.inventory.public_id}/", "/api/items/"):
            with self.subTest(url=url):
                all_rows = self.client.get(url).json()["items"]
                self.assertEqual({row["public_id"] for row in all_rows}, {str(self.item.public_id), str(self.unassigned_item.public_id)})
                rows = self.client.get(url, {"location": str(self.basement.public_id)}).json()["items"]
                self.assertEqual([row["public_id"] for row in rows], [str(self.item.public_id)])
                self.assertEqual(self.client.get(url, {"location": str(self.home.public_id)}).json()["items"], [])
                rows = self.client.get(url, {"location": "unassigned"}).json()["items"]
                self.assertEqual([row["public_id"] for row in rows], [str(self.unassigned_item.public_id)])
                for invalid in ["invalid", str(uuid4()), str(self.archived_location.public_id), str(self.other_location.public_id), str(self.foreign_location.public_id)]:
                    self.assert_invalid(self.client.get(url, {"location": invalid}), "location")

    def test_item_assignment_cannot_bypass_owner_or_archived_inventory_checks(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(self.add_url, self.item_data(location=str(self.basement.public_id))).status_code, 403)
        self.assertEqual(self.client.post(self.edit_url, self.item_data(location=str(self.basement.public_id))).status_code, 403)
        self.client.force_login(self.owner)
        self.inventory.archived_at = timezone.now()
        self.inventory.save()
        self.assertEqual(self.client.post(self.add_url, self.item_data(location=str(self.basement.public_id))).status_code, 404)
        self.assertEqual(self.client.post(self.edit_url, self.item_data(location=str(self.basement.public_id))).status_code, 404)

    def test_model_validation_rejects_blank_archived_and_cross_inventory_locations(self):
        with self.assertRaises(ValidationError):
            Location(inventory=self.inventory, name="  ").full_clean()
        for parent in (self.archived_location, self.other_location, self.foreign_location):
            with self.subTest(parent=parent.name), self.assertRaises(ValidationError):
                Location(inventory=self.inventory, name="New", parent=parent).full_clean()
        for location in (self.archived_location, self.other_location, self.foreign_location):
            with self.subTest(location=location.name), self.assertRaises(ValidationError):
                Item(inventory=self.inventory, name="New", location=location).full_clean()


class ConcurrentLocationMutationTests(TransactionTestCase):
    """Real competing requests must preserve location relationships and guards."""

    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="location-race-owner")
        self.inventory = Inventory.objects.create(owner=self.owner, name="Main")
        self.location = Location.objects.create(inventory=self.inventory, name="Home")
        self.category = Category.objects.create(inventory=self.inventory, name="Electronics")

    def race(self, operations):
        requests = []
        for method, path, payload in operations:
            client = Client(enforce_csrf_checks=True, raise_request_exception=False)
            client.force_login(self.owner)
            token = client.get("/api/auth/csrf/").cookies["csrftoken"].value
            requests.append((client, token, method, path, payload))
        start = Barrier(len(requests))

        def send(request):
            client, token, method, path, payload = request
            connections.close_all()
            try:
                start.wait(timeout=10)
                response = getattr(client, method)(
                    path, data=json.dumps(payload), content_type="application/json",
                    HTTP_X_CSRFTOKEN=token,
                )
                return response.status_code, response.content
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(send, requests))

    def test_competing_sibling_creations_do_not_create_case_variant_duplicates(self):
        url = f"/api/inventory/{self.inventory.public_id}/locations/"
        results = self.race([
            ("post", url, {"name": "Garage"}),
            ("post", url, {"name": " garage "}),
        ])
        statuses = sorted(status for status, _ in results)
        self.assertIn(statuses, ([201, 400], [201, 409]), results)
        self.assertEqual(Location.objects.filter(inventory=self.inventory, name__iexact="Garage", archived_at__isnull=True).count(), 1)

    def test_child_creation_racing_parent_archive_never_leaves_active_child_under_archive(self):
        results = self.race([
            ("post", f"/api/inventory/{self.inventory.public_id}/locations/", {"name": "Basement", "parent_id": str(self.location.public_id)}),
            ("delete", f"/api/location/{self.location.public_id}/", {}),
        ])
        create_status, archive_status = [status for status, _ in results]
        self.assertIn(create_status, (201, 400, 409), results)
        self.assertIn(archive_status, (200, 400, 409), results)
        self.assertTrue(create_status == 201 or archive_status == 200, results)
        self.assertFalse(create_status == 201 and archive_status == 200, results)
        self.location.refresh_from_db()
        active_children = self.location.sub_locations.filter(archived_at__isnull=True).exists()
        self.assertFalse(self.location.archived_at is not None and active_children)

    def test_item_assignment_racing_archive_never_assigns_active_item_to_archive(self):
        results = self.race([
            ("post", f"/api/inventory/{self.inventory.public_id}/add-item/", {
                "name": "Race laptop", "category": str(self.category.pk),
                "purchase_date": "2026-01-15", "purchase_amount": "100.00",
                "condition": "used", "quantity": "1", "location": str(self.location.public_id),
            }),
            ("delete", f"/api/location/{self.location.public_id}/", {}),
        ])
        assignment_status, archive_status = [status for status, _ in results]
        self.assertIn(assignment_status, (200, 400, 409), results)
        self.assertIn(archive_status, (200, 400, 409), results)
        self.assertTrue(assignment_status == 200 or archive_status == 200, results)
        self.assertFalse(assignment_status == 200 and archive_status == 200, results)
        self.location.refresh_from_db()
        assigned = self.location.items.filter(archived_at__isnull=True).exists()
        self.assertFalse(self.location.archived_at is not None and assigned)
