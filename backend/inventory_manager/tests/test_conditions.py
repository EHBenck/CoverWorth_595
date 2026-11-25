from unittest import TestCase

from inventory_manager.pipeline.ebay_client import parse_listings
from inventory_manager.pipeline.poc_valuation import estimate


class EbayConditionTests(TestCase):
    def test_new_and_used_estimates_exclude_other_conditions(self):
        title = "Apple iPhone 13 128GB"

        def summary(condition_id, price):
            return {
                "title": title,
                "conditionId": condition_id,
                "price": {"value": str(price), "currency": "USD"},
                "buyingOptions": ["FIXED_PRICE"],
            }

        rows = parse_listings({
            "itemSummaries": [
                summary("1000", 200),
                summary("1000", 220),
                summary("1000", 240),
                summary("1500", 1),
                summary("1750", 2),
                summary("3000", 100),
                summary("4000", 120),
                summary("5000", 140),
                summary("2000", 400),
                summary("2010", 450),
                summary("2020", 500),
                summary("2030", 550),
                summary("2500", 600),
            ],
        })

        for condition, expected in (("new", 220), ("used", 120)):
            with self.subTest(condition=condition):
                result = estimate(rows, title, want_condition=condition)
                self.assertEqual(result["n"], 3)
                self.assertEqual(result["estimate"], expected)
                self.assertEqual(
                    [row.condition for row in result["comparables"]],
                    [condition] * 3,
                )