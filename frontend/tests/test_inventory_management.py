"""Inventory-management journeys through Settings and the existing switcher."""

import uuid

import pytest
from nicegui import app, ui
from nicegui.testing import User

from tests import app_under_test
from tests.ui_helpers import sign_in

pytestmark = pytest.mark.module_under_test(app_under_test)


def create_inventory(api, name="Office", description="Work equipment") -> str:
    response = api.post("/api/inventories/", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    return response.json()["inventory"]["public_id"]


async def open_management(user: User, account: dict, inventory_id: str) -> None:
    await sign_in(user, account)
    await user.open("/settings")
    await user.should_see("Manage inventories", retries=20)
    await user.should_see(marker=f"inventory-{inventory_id}", retries=20)


async def switcher(user: User):
    await user.should_see(kind=ui.select, retries=20)
    return next(iter(user.find(kind=ui.select).elements))


async def test_settings_requires_sign_in(user: User) -> None:
    await user.open("/settings")
    await user.should_see("Sign in to your account", retries=20)
    await user.should_not_see("Manage inventories")


async def test_settings_lists_owned_inventories_only(user: User, account, api) -> None:
    home_id = api.inventory_id()
    office_id = create_inventory(api)
    other_api = type(api)(api.url)
    other_api.register(f"other_{uuid.uuid4().hex[:8]}")
    foreign_id = create_inventory(other_api, name="Someone else's belongings")

    await open_management(user, account, home_id)
    await user.should_see(marker=f"inventory-{office_id}")
    await user.should_see("Work equipment")
    await user.should_not_see(marker=f"inventory-{foreign_id}")
    await user.should_not_see("Someone else's belongings")
    assert (await switcher(user)).value == home_id


async def test_editing_name_and_description_refreshes_settings_and_switcher(user: User, account, api) -> None:
    home_id = api.inventory_id()
    await open_management(user, account, home_id)
    user.find(marker=f"edit-inventory-{home_id}").click()
    await user.should_see("Edit inventory")
    user.find(marker="edit-inventory-name").clear().type("  Family home  ")
    user.find(marker="edit-inventory-description").clear().type("Furniture and electronics")
    user.find("Save inventory").click()

    await user.should_see("Inventory updated.", retries=20)
    await user.should_see("Family home", retries=20)
    await user.should_see("Furniture and electronics")
    rows = api.get("/api/inventories/").json()["inventories"]
    assert [(row["public_id"], row["name"], row["description"]) for row in rows] == [
        (home_id, "Family home", "Furniture and electronics"),
    ]
    selector = await switcher(user)
    assert selector.value == home_id
    assert selector.options[home_id] == "Family home"


async def test_edit_validation_keeps_dialog_open_and_original_inventory(user: User, account, api) -> None:
    home_id = api.inventory_id()
    create_inventory(api)
    await open_management(user, account, home_id)
    user.find(marker=f"edit-inventory-{home_id}").click()
    user.find(marker="edit-inventory-name").clear().type("   ")
    user.find("Save inventory").click()
    await user.should_see("Inventory name is required.")

    user.find(marker="edit-inventory-name").clear().type(" office ")
    user.find("Save inventory").click()
    await user.should_see("You already have an active inventory with this name.", retries=20)
    await user.should_see("Edit inventory")
    rows = api.get("/api/inventories/").json()["inventories"]
    assert next(row for row in rows if row["public_id"] == home_id)["name"] == "My Inventory"


async def test_archiving_current_inventory_requires_confirmation_and_selects_replacement(user: User, account, api) -> None:
    home_id = api.inventory_id()
    office_id = create_inventory(api)
    await open_management(user, account, home_id)
    user.find(marker=f"archive-inventory-{home_id}").click()
    await user.should_see("Archive inventory?")
    await user.should_see("This is your current inventory. Another available inventory will be selected automatically.")
    dialog = next(iter(user.find(marker="archive-inventory-dialog").elements))
    assert dialog.value is True
    user.find(marker="cancel-inventory-archive").click()
    # NiceGUI's simulator retains closed dialog children in its element tree.
    assert dialog.value is False
    assert len(api.get("/api/inventories/").json()["inventories"]) == 2

    user.find(marker=f"archive-inventory-{home_id}").click()
    user.find("Confirm archive").click()
    await user.should_see("Inventory archived.", retries=20)
    await user.should_see(marker=f"inventory-{office_id}", retries=20)
    await user.should_not_see(marker=f"inventory-{home_id}")
    selector = await switcher(user)
    assert selector.options == {office_id: "Office"}
    assert selector.value == office_id
    assert [row["public_id"] for row in api.get("/api/inventories/").json()["inventories"]] == [office_id]


async def test_archiving_other_inventory_preserves_current_selection(user: User, account, api) -> None:
    home_id = api.inventory_id()
    office_id = create_inventory(api)
    await open_management(user, account, home_id)
    user.find(marker=f"archive-inventory-{office_id}").click()
    await user.should_see("Your current inventory will stay selected.")
    user.find("Confirm archive").click()
    await user.should_see("Inventory archived.", retries=20)
    await user.should_see(marker=f"inventory-{home_id}", retries=20)
    await user.should_not_see(marker=f"inventory-{office_id}")
    selector = await switcher(user)
    assert selector.value == home_id
    assert office_id not in selector.options


async def test_last_inventory_is_disabled_and_existing_new_flow_creates_replacement(user: User, account, api) -> None:
    home_id = api.inventory_id()
    await open_management(user, account, home_id)
    button = next(iter(user.find(marker=f"archive-inventory-{home_id}").elements))
    assert not button.enabled
    await user.should_see("Keep at least one inventory. Use New in the inventory switcher to create a replacement before archiving your last inventory.")

    user.find("New").click()
    await user.should_see("Create Inventory")
    user.find("Inventory name").type("New apartment")
    user.find("Create").click()
    await user.should_see("Created inventory: New apartment", retries=20)
    await user.open("/settings")
    await user.should_see(marker=f"inventory-{home_id}", retries=20)
    assert next(iter(user.find(marker=f"archive-inventory-{home_id}").elements)).enabled
    rows = api.get("/api/inventories/").json()["inventories"]
    assert len(rows) == 2
    replacement = next(row for row in rows if row["name"] == "New apartment")
    assert (await switcher(user)).value == replacement["public_id"]


async def test_management_load_failure_has_working_retry(user: User, account, api, monkeypatch) -> None:
    from utilities import inventory_management

    home_id = api.inventory_id()
    await sign_in(user, account)
    real_url = inventory_management.BACKEND_URL
    monkeypatch.setattr(inventory_management, "BACKEND_URL", "http://127.0.0.1:9")
    await user.open("/settings")
    await user.should_see("Could not load your inventories. Please try again.", retries=20)
    await user.should_see("Retry")
    await user.should_not_see(marker=f"inventory-{home_id}")
    monkeypatch.setattr(inventory_management, "BACKEND_URL", real_url)
    user.find("Retry").click()
    await user.should_see(marker=f"inventory-{home_id}", retries=20)


async def test_stale_page_cannot_archive_the_last_remaining_inventory(user: User, account, api) -> None:
    home_id = api.inventory_id()
    office_id = create_inventory(api)
    await open_management(user, account, home_id)

    # Another session archives Office after Settings has displayed two inventories.
    response = api.post(f"/api/inventories/{office_id}/archive/", json={})
    assert response.status_code == 200, response.text
    user.find(marker=f"archive-inventory-{home_id}").click()
    user.find("Confirm archive").click()

    await user.should_see(
        "You must keep at least one active inventory. Create another inventory before archiving this one.",
        retries=20,
    )
    dialog = next(iter(user.find(marker="archive-inventory-dialog").elements))
    assert dialog.value is True
    assert [row["public_id"] for row in api.get("/api/inventories/").json()["inventories"]] == [home_id]


async def test_expired_session_on_settings_returns_to_login(user: User, account, api) -> None:
    await sign_in(user, account)
    stored = next(iter(app.storage._users.values()))  # pylint: disable=protected-access
    api.session.cookies.clear()
    api.session.cookies.set("sessionid", stored["auth_cookies"]["sessionid"])
    assert api.post("/api/auth/logout/").ok

    await user.open("/settings")
    await user.should_see("Your session expired. Please sign in again.", retries=20)
    await user.should_see("Sign in to your account", retries=20)
    await user.should_not_see("Manage inventories")
