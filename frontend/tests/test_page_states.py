"""Empty, loading, and error states across the signed-in pages (CW-85).

Empty data and failures must look intentional: an empty inventory offers the
next step, a search with no hits says so, and a lost session or server is
reported as such instead of looking like missing data.
"""

import uuid

import pytest
from nicegui import app, ui
from nicegui.testing import User

from tests.fake_ebay import EBAY_NO_MATCHES
from tests.ui_helpers import click_button, sign_in
from utilities.page_states import NOT_ENOUGH_COMPARABLES, SESSION_EXPIRED


def type_in_search(user: User, placeholder: str, text: str) -> None:
    with user:
        fields = [
            field for field in user.find(kind=ui.input).elements
            if field.props.get("placeholder") == placeholder
        ]
    assert fields, f"no search field {placeholder!r}"
    for field in fields:
        field.value = text


async def test_empty_dashboard_offers_the_next_step(user: User, account) -> None:
    await sign_in(user, account)

    await user.should_see("No items yet")
    await user.should_see("No values to chart yet")
    await user.should_see(marker="empty-state")
    await user.should_not_see("items need attention")


async def test_empty_inventory_and_archive_explain_themselves(user: User, account) -> None:
    await sign_in(user, account)

    await user.open("/inventory")
    await user.should_see("No items yet", retries=20)
    await user.should_see("Add your first item to start tracking what you own.")

    with user:
        toggle = next(iter(user.find(kind=ui.toggle).elements))
    toggle.value = "archived"
    await user.should_see("No archived items", retries=20)


async def test_inventory_search_with_no_results_can_be_cleared(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    await sign_in(user, account)

    await user.open("/inventory")
    await user.should_see(marker=f"inventory-item-{item_id}", retries=20)
    type_in_search(user, "Search your inventory...", "zzz-nothing")

    await user.should_see('No results for "zzz-nothing"', retries=20)
    await user.should_not_see("No items yet")
    click_button(user, "Clear filters")
    await user.should_see(marker=f"inventory-item-{item_id}", retries=20)


async def test_category_search_with_no_results_differs_from_no_categories(user: User, account, api) -> None:
    api.create_category("Electronics")
    await sign_in(user, account)

    await user.open("/categories")
    await user.should_see("Electronics", retries=20)
    type_in_search(user, "Search categories...", "zzz-nothing")

    await user.should_see('No results for "zzz-nothing"', retries=20)
    await user.should_not_see("No categories yet")


async def test_empty_locations_explain_how_to_add_one(user: User, account, api) -> None:
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    await user.open(f"/add-item/{inventory_id}")
    await user.should_see("No locations yet. Use Manage Locations", retries=20)
    user.find(marker="manage-locations").click()
    await user.should_see("Create one below to record where your items are kept.", retries=20)


async def test_insufficient_comparables_are_explained(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone(name=f"Widget {EBAY_NO_MATCHES}")
    await sign_in(user, account)

    await user.open("/valuations")
    await user.should_see(f"Widget {EBAY_NO_MATCHES}", retries=20)
    click_button(user, "Update")

    await user.should_see(NOT_ENOUGH_COMPARABLES, retries=20)
    await user.should_see("No valuation available")
    assert api.item(item_id).json()["item"]["current_estimated_amount"] is None


async def test_reports_for_an_empty_inventory(user: User, account) -> None:
    await sign_in(user, account)

    await user.open("/reports")
    await user.should_see("Nothing to report yet", retries=20)
    await user.should_not_see("Generate Report")


@pytest.mark.parametrize("path", [
    "/inventory",
    "/categories",
    "/valuations",
    "/reports",
    f"/item/{uuid.uuid4()}",
    f"/edit-item/{uuid.uuid4()}",
])
async def test_expired_session_on_any_page_returns_to_login(user: User, account, api, path: str) -> None:
    await sign_in(user, account)

    # End the Django session behind the frontend's back (e.g. signed out elsewhere).
    stored = next(iter(app.storage._users.values()))  # pylint: disable=protected-access
    api.session.cookies.clear()
    api.session.cookies.set("sessionid", stored["auth_cookies"]["sessionid"])
    assert api.post("/api/auth/logout/").ok

    await user.open(path)
    await user.should_see(SESSION_EXPIRED, retries=20)
    await user.should_see("Sign in to your account")
