"""Current values must agree across pages and change only after acceptance.

These workflows use the real temporary Django server. Only its eBay HTTP
responses use the recorded fixture already configured by conftest.py.
"""

import asyncio

import pytest
from nicegui import ui
from nicegui.testing import User

from tests import app_under_test
from tests.ui_helpers import click_button, set_value, sign_in


pytestmark = pytest.mark.module_under_test(app_under_test)


async def assert_value(user: User, marker: str, value: str) -> None:
    await user.should_see(marker=marker, content=value, retries=20)
    with user:
        labels = user.find(marker=marker).elements
        assert len(labels) == 1
        assert next(iter(labels)).text == value


async def request_and_accept(user: User) -> None:
    click_button(user, "Update")
    await user.should_see("Live estimate: $247.00", retries=20)
    click_button(user, "Accept $247.00")
    await user.should_see("Valuation saved: $247.00", retries=20)


async def wait_for_saved_item(api, item_id: str, **expected) -> dict:
    """A previous save toast can still exist; wait for this save's persisted state."""
    for _ in range(200):
        await asyncio.sleep(0.02)
        saved = api.item(item_id).json()["item"]
        if all(saved.get(key) == value for key, value in expected.items()):
            return saved
    raise AssertionError(f"Item did not persist {expected!r}: {saved!r}")


def accept_fixture_estimate(api, item_id: str) -> None:
    response = api.post(f"/api/item/{item_id}/valuation/")
    assert response.status_code == 200, response.text
    response = api.post(
        f"/api/item/{item_id}/valuation/accept/",
        json={"valuation_run_id": response.json()["valuation_run_id"]},
    )
    assert response.status_code == 200, response.text


async def test_preview_and_cancel_preserve_current_value(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    await sign_in(user, account)
    await user.open("/valuations")
    await assert_value(user, f"valuation-value-{item_id}", "$799.00")

    click_button(user, "Update")
    await user.should_see("Live estimate: $247.00", retries=20)
    await user.should_see("Accept $247.00")
    await assert_value(user, f"valuation-value-{item_id}", "$799.00")
    saved = api.item(item_id).json()["item"]
    assert saved["manual_value"] is None
    assert saved["current_estimated_amount"] is None
    assert saved["effective_value"] == "799.00"
    assert saved["effective_value_source"] == "purchase"

    click_button(user, "Cancel")
    await user.should_see("Valuation preview cancelled.", retries=20)
    await user.should_see("No valuation available", retries=20)
    await user.should_not_see(kind=ui.button, content="Accept $247.00")
    await assert_value(user, f"valuation-value-{item_id}", "$799.00")
    click_button(user, "No valuation available")
    await user.should_see("Please update an item's valuation first.", retries=20)
    assert api.item(item_id).json()["item"]["current_estimated_amount"] is None


async def test_accept_updates_all_pages_and_survives_unrelated_edit(
    user: User, account, api,
) -> None:
    api.create_category("Phones")
    # An explicit/manual or legacy autofilled amount must be replaced by Accept.
    item_id = api.add_phone(manual_value="1000.00")
    await sign_in(user, account)
    await user.open("/valuations")
    await assert_value(user, f"valuation-value-{item_id}", "$1,000.00")
    await request_and_accept(user)
    await assert_value(user, f"valuation-value-{item_id}", "$247.00")

    saved = await wait_for_saved_item(api, item_id, manual_value=None, effective_value="247.00")
    assert saved["manual_value"] is None
    assert saved["current_estimated_amount"] == saved["effective_value"] == "247.00"
    assert saved["effective_value_source"] == "estimated"

    await user.open(f"/item/{item_id}")
    await assert_value(user, "current-item-value", "$247.00")
    await assert_value(user, "current-value-source", "Accepted estimate")
    await user.open("/inventory")
    await assert_value(user, f"item-value-{item_id}", "$247.00")
    await user.open("/dashboard")
    await user.should_see("$247.00", retries=20)
    assert api.get("/api/dashboard/").json()["summary"]["estimated_value"] == 247.0
    await user.open("/valuations")
    await assert_value(user, f"valuation-value-{item_id}", "$247.00")

    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Save Changes", retries=20)
    set_value(user, "Notes", "An unrelated edit must retain the accepted estimate.")
    click_button(user, "Save Changes")
    await user.should_see("Item updated successfully.", retries=20)
    saved = await wait_for_saved_item(
        api, item_id,
        notes="An unrelated edit must retain the accepted estimate.",
    )
    assert saved["manual_value"] is None
    assert saved["effective_value"] == "247.00"
    # Edit Item intentionally navigates after its success notification.
    await assert_value(user, f"item-value-{item_id}", "$247.00")
    await user.open(f"/item/{item_id}")
    await assert_value(user, "current-item-value", "$247.00")


async def test_manual_zero_override_and_clear_agree_across_pages(
    user: User, account, api,
) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    accept_fixture_estimate(api, item_id)
    await sign_in(user, account)
    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Save Changes", retries=20)
    set_value(user, "Manual Value ($)", 0)
    user.find("Manual Value ($)").trigger("blur")
    click_button(user, "Save Changes")
    await user.should_see("Item updated successfully.", retries=20)

    saved = await wait_for_saved_item(api, item_id, manual_value="0.00", effective_value="0.00")
    assert saved["current_estimated_amount"] == "247.00"
    assert saved["effective_value"] == "0.00"
    assert saved["effective_value_source"] == "manual"
    # Wait for the existing delayed success navigation before opening another page.
    await assert_value(user, f"item-value-{item_id}", "$0.00")
    await user.open("/valuations")
    await assert_value(user, f"valuation-value-{item_id}", "$0.00")
    await user.open(f"/item/{item_id}")
    await assert_value(user, "current-item-value", "$0.00")
    await assert_value(user, "current-value-source", "Manual value")

    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Save Changes", retries=20)
    set_value(user, "Manual Value ($)", None)
    user.find("Manual Value ($)").trigger("blur")
    click_button(user, "Save Changes")
    await user.should_see("Item updated successfully.", retries=20)
    saved = await wait_for_saved_item(api, item_id, manual_value=None, effective_value="247.00")
    assert saved["manual_value"] is None
    assert saved["effective_value"] == "247.00"
    await assert_value(user, f"item-value-{item_id}", "$247.00")
    await user.open(f"/item/{item_id}")
    await assert_value(user, "current-value-source", "Accepted estimate")


async def test_edit_numeric_fields_blur_round_and_save(
    user: User, account, api,
) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    await sign_in(user, account)

    # Leaving a numeric field invokes NiceGUI's sanitizer, as a browser Tab does.
    # Exercise rounding, fixed decimal display, minimum quantity, zero, and blank.
    for purchase, manual, quantity, saved_purchase, saved_manual, saved_quantity in (
        (1234.567, 98.7, 0, "1234.57", "98.70", 1),
        (0, None, 2, "0.00", None, 2),
    ):
        await user.open(f"/edit-item/{item_id}")
        await user.should_see("Save Changes", retries=20)
        for label, value in (
            ("Purchase Price ($) *", purchase),
            ("Manual Value ($)", manual),
            ("Quantity", quantity),
        ):
            set_value(user, label, value)
            user.find(label).trigger("blur")

        with user:
            for label, amount in (
                ("Purchase Price ($) *", saved_purchase),
                ("Manual Value ($)", saved_manual),
            ):
                fields = user.find(label).elements
                assert len(fields) == 1
                field = next(iter(fields))
                assert field.value == (float(amount) if amount is not None else None)
                assert field.props["model-value"] == amount
            quantity_fields = user.find("Quantity").elements
            assert len(quantity_fields) == 1
            assert next(iter(quantity_fields)).value == saved_quantity

        click_button(user, "Save Changes")
        await user.should_see("Item updated successfully.", retries=20)
        saved = await wait_for_saved_item(
            api, item_id, purchase_amount=saved_purchase,
            manual_value=saved_manual, quantity=saved_quantity,
        )
        expected_value = saved_manual if saved_manual is not None else saved_purchase
        assert saved["effective_value"] == expected_value
        # Wait for the existing success redirect before beginning the next edit.
        await assert_value(user, f"item-value-{item_id}", f"${float(expected_value):,.2f}")


@pytest.mark.parametrize("amount", ["0.00", "247.35"])
async def test_accepted_amount_retains_cents_after_reload(
    user: User, account, api, seed_backend, amount,
) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    seed_backend(f"""
        from decimal import Decimal
        from myapp.models import Item, ValuationRun
        item = Item.objects.get(public_id={item_id!r})
        ValuationRun.objects.create(
            item=item, requested_by=item.inventory.owner, status='success',
            valuation_type='automated', estimated_amount=Decimal({amount!r}),
        )
    """)
    run = api.get(f"/api/item/{item_id}/valuation/history/").json()["history"][0]
    response = api.post(
        f"/api/item/{item_id}/valuation/accept/",
        json={"valuation_run_id": run["valuation_run_id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["effective_value"] == amount
    detail = api.item(item_id).json()["item"]
    assert detail["current_estimated_amount"] == amount
    assert detail["effective_value"] == amount
    expected = f"${float(amount):,.2f}"
    await sign_in(user, account)
    await user.open("/inventory")
    await assert_value(user, f"item-value-{item_id}", expected)
    await user.open("/valuations")
    await assert_value(user, f"valuation-value-{item_id}", expected)
    await user.open(f"/item/{item_id}")
    await assert_value(user, "current-item-value", expected)
    await assert_value(user, "current-value-source", "Accepted estimate")

    for path in ("/dashboard", "/categories", "/reports"):
        await user.open(path)
        await user.should_see(expected, retries=20)
        with user:
            labels = {label.text for label in user.find(kind=ui.label).elements}
        assert expected in labels, (path, labels)
    await user.should_see(f"Estimated value: {expected}")
