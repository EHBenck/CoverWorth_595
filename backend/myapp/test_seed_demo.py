"""CW86: repeatable, scoped development demo data."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from myapp.management.commands.seed_demo import DEMO_EMAIL, DEMO_USERNAME, demo_id
from myapp.models import Category, Inventory, Item, Location, ValuationRun


@override_settings(DEBUG=True)
class DemoSeedCommandTests(TestCase):
    def seed(self, **kwargs):
        output = StringIO()
        with patch.dict("os.environ", {"COVERWORTH_DEMO_PASSWORD": "SeedPassword!482Secure"}):
            call_command("seed_demo", stdout=output, **kwargs)
        return output.getvalue()

    def test_creates_login_inventories_categories_locations_items_and_valuations(self):
        output = self.seed()
        self.assertIn("10 items", output)
        user = get_user_model().objects.get(username=DEMO_USERNAME)
        self.assertEqual(user.email, DEMO_EMAIL)
        self.assertTrue(user.check_password("SeedPassword!482Secure"))
        self.assertEqual(Inventory.objects.filter(owner=user).count(), 2)
        self.assertEqual(Category.objects.filter(inventory__owner=user).count(), 7)
        self.assertEqual(Location.objects.filter(inventory__owner=user).count(), 9)
        self.assertEqual(Item.objects.filter(inventory__owner=user).count(), 10)
        self.assertEqual(ValuationRun.objects.filter(item__inventory__owner=user).count(), 5)

        for item in Item.objects.filter(inventory__owner=user).select_related(
            "inventory", "category", "location"
        ):
            self.assertEqual(item.category.inventory_id, item.inventory_id)
            self.assertEqual(item.location.inventory_id, item.inventory_id)
            self.assertIsNotNone(item.effective_value)
        desk = Location.objects.get(public_id=demo_id("location", "home", "desk"))
        self.assertEqual(desk.path, "Home → Office → Desk")
        for run in ValuationRun.objects.filter(item__inventory__owner=user):
            self.assertEqual(run.input_snapshot["demo_fixture"], True)
            self.assertEqual(run.algorithm_version, "demo-seed-v1")

    def test_rerun_restores_fixture_fields_without_duplicates_or_password_rotation(self):
        self.seed()
        user = get_user_model().objects.get(username=DEMO_USERNAME)
        first_password_hash = user.password
        original_ids = set(Item.objects.values_list("public_id", flat=True))
        target_id = demo_id("item", "home", "laptop")
        item = Item.objects.get(public_id=target_id)
        item.manual_value = None
        item.description = "changed in UI"
        item.save(update_fields=["manual_value", "description"])
        self.seed()
        user.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(user.password, first_password_hash)
        self.assertEqual(str(item.manual_value), "850.00")
        self.assertIn("charger", item.description)
        self.assertEqual(set(Item.objects.values_list("public_id", flat=True)), original_ids)
        self.assertEqual(ValuationRun.objects.count(), 5)

    def test_reset_drops_only_the_two_demo_inventories(self):
        self.seed()
        user = get_user_model().objects.get(username=DEMO_USERNAME)
        inventory = Inventory.objects.get(public_id=demo_id("inventory", "home"))
        Item.objects.create(inventory=inventory, name="Additional testing item")
        custom = Inventory.objects.create(owner=user, name="My custom demo work")
        Item.objects.create(inventory=custom, name="Keep this")
        other_user = get_user_model().objects.create_user(username="a_real_user", password="Testpassword123!")
        unrelated = Inventory.objects.create(owner=other_user, name="Private inventory")
        Item.objects.create(inventory=unrelated, name="Do not touch")

        self.seed(reset=True)
        self.assertEqual(Item.objects.filter(inventory__owner=user).count(), 11)
        self.assertFalse(Item.objects.filter(name="Additional testing item").exists())
        self.assertTrue(Item.objects.filter(inventory=custom, name="Keep this").exists())
        self.assertTrue(Item.objects.filter(inventory=unrelated, name="Do not touch").exists())
        self.assertEqual(ValuationRun.objects.filter(item__inventory__owner=user).count(), 5)

    @override_settings(DEBUG=False)
    def test_refuses_production_mode(self):
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            self.seed()
        self.assertFalse(get_user_model().objects.filter(username=DEMO_USERNAME).exists())

    def test_refuses_to_repurpose_an_existing_account(self):
        get_user_model().objects.create_user(username=DEMO_USERNAME, email="private@example.org")
        with self.assertRaisesMessage(CommandError, "different or privileged account"):
            self.seed()
        self.assertFalse(Inventory.objects.exists())

    def test_first_run_generates_password_and_does_not_rotate_on_rerun(self):
        stdout = StringIO()
        with patch.dict("os.environ", {"COVERWORTH_DEMO_PASSWORD": ""}):
            call_command("seed_demo", stdout=stdout)
        prefix = "Generated demo password (shown once): "
        self.assertIn(prefix, stdout.getvalue())
        generated_password = stdout.getvalue().split(prefix, 1)[1].strip().splitlines()[0]
        user = get_user_model().objects.get(username=DEMO_USERNAME)
        self.assertTrue(user.check_password(generated_password))
        previous_hash = user.password
        stdout = StringIO()
        with patch.dict("os.environ", {"COVERWORTH_DEMO_PASSWORD": ""}):
            call_command("seed_demo", stdout=stdout)
        user.refresh_from_db()
        self.assertEqual(user.password, previous_hash)
        self.assertIn("password preserved", stdout.getvalue())
