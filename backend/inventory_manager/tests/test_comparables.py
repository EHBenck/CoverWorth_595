from decimal import Decimal
from unittest import TestCase

from inventory_manager.pipeline.poc_valuation import estimate
from inventory_manager.pipeline.schemas import Listing


class ComparableFallbackTests(TestCase):
    def setUp(self):
        self.complete_units = [
            Listing("Shark NV352 Navigator Lift-Away Upright Vacuum", Decimal("60"), "used"),
            Listing("Shark Navigator Lift-Away NV352 Upright Vacuum", Decimal("70"), "used"),
            Listing("Navigator Lift-Away Shark Upright Vacuum NV352", Decimal("80"), "used"),
        ]
        self.other_listings = [
            Listing(
                "Shark Navigator Lift-Away NV350 NV351 NV352 Motor Body Assembly OEM",
                Decimal("21.24"),
                "used",
            ),
            Listing("Shark NV360 Navigator Lift-Away Upright Vacuum", Decimal("50"), "used"),
            Listing("Shark NV352 Navigator Lift-Away Upright Vacuum", Decimal("120"), "new"),
        ]

    def estimate_shark(self, rows):
        return estimate(
            rows,
            "Shark Navigator Lift-Away Shark NV352",
            item_name="Shark Navigator Lift-Away",
            brand="Shark",
            model_number="NV352",
        )

    def test_two_complete_units_are_insufficient(self):
        result = self.estimate_shark(self.complete_units[:2] + self.other_listings)

        self.assertEqual(result["comparables"], self.complete_units[:2])
        self.assertIsNone(result["estimate"])
        self.assertEqual(
            result["message"],
            "Found 2 matching used listings. At least 3 are needed for an estimate.",
        )

    def test_three_complete_units_produce_a_median(self):
        result = self.estimate_shark(self.complete_units + self.other_listings)

        self.assertEqual(result["comparables"], self.complete_units)
        self.assertEqual(result["estimate"], 70)

    def test_broad_name_asks_for_more_details(self):
        result = estimate(self.complete_units, "vacuum", item_name="vacuum")

        self.assertIsNone(result["estimate"])
        self.assertEqual(result["n"], 0)
        self.assertIn("Add a brand and model number", result["message"])