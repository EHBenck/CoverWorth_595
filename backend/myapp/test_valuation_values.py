"""Value selection and acceptance regressions through the public item APIs.

Saved runs in these tests are synthetic fixtures. The one preview request uses
the existing recorded eBay HTTP fixture, never a live marketplace call.
"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from myapp.models import Item, ValuationRun
from myapp.test_sprint4_integration import Sprint4Client, fake_ebay, phone_item


class ValuationValueWorkflowTestCase(TestCase):
    def setUp(self):
        self.frontend = Sprint4Client()
        self.assertEqual(self.frontend.register("valuation_value_owner").status_code, 201)
        self.inventory_id = self.frontend.active_inventory_id()
        self.category = self.frontend.create_category(self.inventory_id, "Phones")
        response = self.frontend.add_item(
            self.inventory_id,
            phone_item(self.category.id, purchase_amount="1000.00"),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.item = Item.objects.get(public_id=response.json()["item_id"])
        self.item_id = str(self.item.public_id)

    def saved_run(self, amount="247.00", **overrides):
        return ValuationRun.objects.create(
            **{
                "item": self.item,
                "requested_by": self.item.inventory.owner,
                "status": "success",
                "estimated_amount": Decimal(amount) if amount is not None else None,
                "algorithm_version": "synthetic-value-regression",
                **overrides,
            }
        )

    def accept(self, run):
        response = self.frontend.accept_valuation(self.item_id, str(run.public_id))
        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        return response.json()

    def edit(self, *, manual="", omit_manual=False, as_json=False, **overrides):
        payload = phone_item(
            self.category.id,
            purchase_amount="1000.00",
            manual_value=manual,
            **overrides,
        )
        if omit_manual:
            payload.pop("manual_value")
        send = self.frontend.post_json if as_json else self.frontend.post_form
        return send(f"/api/item/{self.item_id}/edit/", payload)

    def assert_money(self, actual, expected, description):
        if expected is None:
            self.assertIsNone(actual, description)
        else:
            self.assertIsNotNone(actual, description)
            self.assertEqual(Decimal(str(actual)), Decimal(expected), description)

    def assert_current_value(self, amount, source):
        """Compare actual responses used by every current-value surface."""
        detail_response = self.frontend.get(f"/api/item/{self.item_id}/")
        inventory_response = self.frontend.get(f"/api/inventory/{self.inventory_id}/")
        list_response = self.frontend.get("/api/items/")
        dashboard_response = self.frontend.get("/api/dashboard/")
        categories_response = self.frontend.get(
            f"/api/inventory/{self.inventory_id}/categories/"
        )
        for response in (detail_response, inventory_response, list_response,
                         dashboard_response, categories_response):
            self.assertEqual(response.status_code, 200, response.content)

        detail = detail_response.json()["item"]
        inventory = next(row for row in inventory_response.json()["items"]
                         if row["public_id"] == self.item_id)
        listing = next(row for row in list_response.json()["items"]
                       if row["public_id"] == self.item_id)
        for label, row in (("item detail", detail), ("inventory detail", inventory),
                           ("item list", listing)):
            self.assert_money(row["effective_value"], amount, label)
            self.assertEqual(row["effective_value_source"], source, label)
        self.assert_money(listing["estimated_value"], amount, "item list display alias")

        total = amount if amount is not None else "0.00"
        dashboard = dashboard_response.json()
        self.assert_money(dashboard["summary"]["estimated_value"], total, "dashboard total")
        dashboard_category = next(row for row in dashboard["category_data"]
                                  if row["name"] == self.category.name)
        self.assert_money(dashboard_category["value"], total, "dashboard category total")
        category = next(row for row in categories_response.json()["categories"]
                        if row["public_id"] == str(self.category.public_id))
        self.assert_money(category["total_value"], total, "category management total")
        return detail, inventory, listing

    def test_blank_manual_value_falls_back_without_persisting_an_override(self):
        self.assertIsNone(self.item.manual_value)
        self.assertIsNone(self.item.current_estimated_amount)
        self.assert_current_value("1000.00", "purchase")

    def test_requesting_an_estimate_leaves_current_values_unchanged_until_accept(self):
        before = (self.item.manual_value, self.item.current_estimated_amount,
                  self.item.valuation_date, self.item.updated_at)
        with fake_ebay():
            response = self.frontend.run_valuation(self.item_id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["estimate"], 247.0)
        self.assertTrue(response.json()["valuation_run_id"])
        self.item.refresh_from_db()
        self.assertEqual((self.item.manual_value, self.item.current_estimated_amount,
                          self.item.valuation_date, self.item.updated_at), before)
        self.assert_current_value("1000.00", "purchase")

    def test_accept_updates_every_current_value_surface_and_preserves_purchase(self):
        run = self.saved_run()
        saved = self.accept(run)
        self.assert_money(saved["estimated_value"], "247.00", "accept response")
        self.assert_money(saved["effective_value"], "247.00", "accept canonical value")
        self.assertEqual(saved["effective_value_source"], "estimated")
        self.assertIsNone(self.item.manual_value)
        self.assertEqual(self.item.current_estimated_amount, Decimal("247.00"))
        self.assertEqual(self.item.purchase_amount, Decimal("1000.00"))
        self.assertIsNotNone(self.item.valuation_date)
        self.assert_current_value("247.00", "estimated")
        self.assertEqual(ValuationRun.objects.get(pk=run.pk).estimated_amount, Decimal("247.00"))

    def test_accept_explicitly_replaces_legacy_or_deliberate_manual_override(self):
        run = self.saved_run()
        for manual in ("1000.00", "350.00", "0.00"):
            with self.subTest(manual=manual):
                # Purchase-equal legacy values cannot safely be inferred as automatic.
                self.item.manual_value = Decimal(manual)
                self.item.current_estimated_amount = None
                self.item.save(update_fields=["manual_value", "current_estimated_amount"])
                self.assert_current_value(manual, "manual")
                self.accept(run)
                self.assertIsNone(self.item.manual_value)
                self.assert_current_value("247.00", "estimated")

    def test_unrelated_edits_do_not_restore_purchase_price_after_acceptance(self):
        self.accept(self.saved_run())
        for omit_manual in (False, True):
            with self.subTest(omit_manual=omit_manual):
                response = self.edit(omit_manual=omit_manual, notes="Updated notes")
                self.assertEqual(response.status_code, 200, response.content)
                self.item.refresh_from_db()
                self.assertEqual(self.item.notes, "Updated notes")
                self.assertIsNone(self.item.manual_value)
                self.assert_current_value("247.00", "estimated")

    def test_omitted_manual_value_on_edit_preserves_explicit_override(self):
        for manual in ("350.00", "0.00"):
            with self.subTest(manual=manual):
                self.item.manual_value = Decimal(manual)
                self.item.current_estimated_amount = Decimal("247.00")
                self.item.save(update_fields=["manual_value", "current_estimated_amount"])
                response = self.edit(omit_manual=True, notes="Keep override")
                self.assertEqual(response.status_code, 200, response.content)
                self.item.refresh_from_db()
                self.assertEqual(self.item.manual_value, Decimal(manual))
                self.assert_current_value(manual, "manual")

    def test_explicit_blank_or_json_null_clears_override_and_restores_estimate(self):
        for manual, as_json in (("", False), (None, True)):
            with self.subTest(manual=manual, as_json=as_json):
                self.item.manual_value = Decimal("350.00")
                self.item.current_estimated_amount = Decimal("247.00")
                self.item.save(update_fields=["manual_value", "current_estimated_amount"])
                response = self.edit(manual=manual, as_json=as_json)
                self.assertEqual(response.status_code, 200, response.content)
                self.item.refresh_from_db()
                self.assertIsNone(self.item.manual_value)
                self.assert_current_value("247.00", "estimated")

    def test_new_manual_override_can_replace_accepted_value_and_be_cleared(self):
        self.accept(self.saved_run())
        response = self.edit(manual="350.00")
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_current_value("350.00", "manual")
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_estimated_amount, Decimal("247.00"))
        response = self.edit(manual="")
        self.assertEqual(response.status_code, 200, response.content)
        self.assert_current_value("247.00", "estimated")

    def test_zero_purchase_estimate_and_manual_values_remain_distinct_from_missing(self):
        cases = (
            (None, None, None, None, None),
            (None, None, "0.00", "0.00", "purchase"),
            (None, "0.00", "1000.00", "0.00", "estimated"),
            ("0.00", "247.00", "1000.00", "0.00", "manual"),
        )
        for manual, estimate, purchase, amount, source in cases:
            with self.subTest(source=source):
                self.item.manual_value = Decimal(manual) if manual is not None else None
                self.item.current_estimated_amount = Decimal(estimate) if estimate is not None else None
                self.item.purchase_amount = Decimal(purchase) if purchase is not None else None
                self.item.save(update_fields=["manual_value", "current_estimated_amount", "purchase_amount"])
                detail, inventory, _ = self.assert_current_value(amount, source)
                if estimate == "0.00":
                    self.assertEqual(detail["current_estimated_amount"], "0.00")
                    self.assertEqual(inventory["current_estimated_amount"], "0.00")

    def test_accepting_zero_estimate_clears_override_and_persists_zero(self):
        self.item.manual_value = Decimal("350.00")
        self.item.save(update_fields=["manual_value"])
        saved = self.accept(self.saved_run("0.00"))
        self.assert_money(saved["estimated_value"], "0.00", "zero accept response")
        self.assertIsNone(self.item.manual_value)
        self.assertEqual(self.item.current_estimated_amount, Decimal("0.00"))
        self.assert_current_value("0.00", "estimated")

    def test_negative_manual_edit_does_not_change_an_existing_accepted_value(self):
        self.accept(self.saved_run())
        response = self.edit(manual="-1.00", notes="Must not save")
        self.assertEqual(response.status_code, 400, response.content)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.notes, "Must not save")
        self.assertIsNone(self.item.manual_value)
        self.assert_current_value("247.00", "estimated")

    def test_rejected_acceptance_preserves_current_manual_and_estimated_values(self):
        self.item.manual_value = Decimal("350.00")
        self.item.current_estimated_amount = Decimal("200.00")
        self.item.valuation_date = timezone.now()
        self.item.save()
        before = (self.item.manual_value, self.item.current_estimated_amount,
                  self.item.valuation_date, self.item.updated_at)
        failed = self.saved_run(status="failed")
        absent = self.saved_run(amount=None)
        another = Item.objects.create(inventory=self.item.inventory, name="Other item")
        other_run = self.saved_run(item=another)
        cases = ((str(failed.public_id), 404), (str(absent.public_id), 400),
                 (str(other_run.public_id), 404), (str(uuid4()), 404), ("not-a-uuid", 400))
        for run_id, status in cases:
            with self.subTest(run_id=run_id):
                response = self.frontend.accept_valuation(self.item_id, run_id)
                self.assertEqual(response.status_code, status, response.content)
                self.item.refresh_from_db()
                self.assertEqual((self.item.manual_value, self.item.current_estimated_amount,
                                  self.item.valuation_date, self.item.updated_at), before)
        self.assert_current_value("350.00", "manual")

    def test_foreign_or_archived_item_cannot_have_its_override_cleared_by_acceptance(self):
        self.item.manual_value = Decimal("350.00")
        self.item.save(update_fields=["manual_value"])
        run = self.saved_run()
        intruder = Sprint4Client()
        self.assertEqual(intruder.register("valuation_value_intruder").status_code, 201)
        response = intruder.accept_valuation(self.item_id, str(run.public_id))
        self.assertEqual(response.status_code, 404, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.manual_value, Decimal("350.00"))
        self.assertIsNone(self.item.current_estimated_amount)

        self.item.archived_at = timezone.now()
        self.item.save(update_fields=["archived_at"])
        response = self.frontend.accept_valuation(self.item_id, str(run.public_id))
        self.assertEqual(response.status_code, 404, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.manual_value, Decimal("350.00"))
        self.assertIsNone(self.item.current_estimated_amount)
