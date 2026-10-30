"""Physical-location workflows through NiceGUI and the live Django backend.

These tests exercise real HTTP requests against the disposable database supplied
by conftest.py. They do not use or alter the development database.
"""

import asyncio
import base64
import uuid

import pytest
import requests
from nicegui import app, ui
from nicegui.testing import User

from tests import app_under_test
from tests.ui_helpers import set_value, sign_in, upload_file


pytestmark = pytest.mark.module_under_test(app_under_test)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


def marked(user: User, marker: str):
    return next(iter(user.find(marker=marker).elements))


def set_marked_value(user: User, marker: str, value) -> None:
    with user:
        marked(user, marker).value = value


async def wait_for_control(user: User, marker: str) -> None:
    """Let asynchronous dialog refreshes finish before typing into disabled inputs."""
    for _ in range(250):
        await asyncio.sleep(0.02)
        if marked(user, marker).enabled:
            return
    raise AssertionError(f"Control {marker!r} did not become available")


async def wait_for_exact_label(user: User, text: str) -> None:
    """Avoid matching an instructional example or the editable input value."""
    for _ in range(250):
        await asyncio.sleep(0.02)
        if any(label.text == text for label in user.find(kind=ui.label).elements):
            return
    raise AssertionError(f"Label {text!r} was not rendered")


def locations(api, inventory_id: str | None = None) -> list[dict]:
    response = api.get(f"/api/inventory/{inventory_id or api.inventory_id()}/locations/")
    assert response.status_code == 200, response.text
    return response.json()["locations"]


def create_location(api, name: str, parent: dict | None = None, inventory_id: str | None = None) -> dict:
    response = api.post(
        f"/api/inventory/{inventory_id or api.inventory_id()}/locations/",
        json={"name": name, "parent_id": parent["public_id"] if parent else None},
    )
    assert response.status_code == 201, response.text
    return response.json()["location"]


def archive_location(api, location: dict):
    return api.session.delete(
        f"{api.url}/api/location/{location['public_id']}/",
        headers=api._headers(),
        timeout=5,
    )


async def open_add_item(user: User, account, api, *, sign_in_first: bool = True) -> None:
    if sign_in_first:
        await sign_in(user, account)
    await user.open(f"/add-item/{api.inventory_id()}")
    await user.should_see(marker="item-location", retries=30)
    await wait_for_control(user, "item-location")


def fill_item(user: User, api, name: str) -> None:
    user.find("Item Name *").type(name)
    set_value(user, "Category *", str(api.category_id()))
    set_value(user, "Date Acquired *", "2026-01-15")
    set_value(user, "Purchase Price ($) *", 1200)


async def open_manager(user: User) -> None:
    user.find(marker="manage-locations").click()
    await user.should_see(marker="location-name", retries=30)
    await wait_for_control(user, "location-name")
    assert marked(user, "location-management-dialog").value is True


async def create_through_dialog(user: User, api, name: str, parent: dict | None = None) -> dict:
    user.find(marker="location-name").clear().type(name)
    set_marked_value(user, "location-parent", parent["public_id"] if parent else "")
    user.find(marker="save-location").click()
    expected_path = f"{parent['path']} → {name.strip()}" if parent else name.strip()
    # Wait for the rendered list row, not a notification left by a previous save.
    await wait_for_exact_label(user, expected_path)
    result = next(row for row in locations(api) if row["path"] == expected_path)
    await user.should_see(marker=f"location-{result['public_id']}", retries=30)
    await wait_for_control(user, "location-name")
    return result


async def test_create_hierarchy_and_assign_on_add_preserves_unsaved_fields(user: User, account, api) -> None:
    api.create_category("Electronics")
    await open_add_item(user, account, api)
    fill_item(user, api, "Laptop for basement")
    user.find(kind=ui.textarea, content="Notes").type("Keep the charger with it")
    upload_file(user, "basement-laptop.png", PNG, "image/png")
    await user.should_see("Photo 'basement-laptop.png' selected.", retries=30)

    await open_manager(user)
    home = await create_through_dialog(user, api, "Home")
    basement = await create_through_dialog(user, api, "Basement", home)
    user.find(marker="close-location-management").click()

    assert marked(user, "location-management-dialog").value is False
    assert marked(user, "item-location").value == basement["public_id"]
    assert next(iter(user.find("Item Name *").elements)).value == "Laptop for basement"
    assert next(iter(user.find(kind=ui.textarea, content="Notes").elements)).value == "Keep the charger with it"
    user.find(kind=ui.button, content="Add Item").click()
    await user.should_see("Item added successfully.", retries=30)

    item = api.get("/api/items/").json()["items"][0]
    assert item["location_id"] == basement["public_id"]
    assert item["location"] == "Home → Basement"
    detail = api.item(item["public_id"]).json()["item"]
    assert detail["notes"] == "Keep the charger with it"
    assert [row["original_filename"] for row in api.attachments(item["public_id"])] == ["basement-laptop.png"]
    await user.open(f"/item/{item['public_id']}")
    await user.should_see("Item Information", retries=30)
    await user.should_see("Home → Basement")


async def test_edit_reassigns_and_clears_optional_location(user: User, account, api) -> None:
    api.create_category("Electronics")
    home = create_location(api, "Home")
    bedroom = create_location(api, "Bedroom", home)
    storage = create_location(api, "Storage Unit")
    shelf = create_location(api, "Shelf A", storage)
    item_id = api.add_phone(name="Camera", location=bedroom["public_id"])
    await sign_in(user, account)

    await user.open(f"/edit-item/{item_id}")
    await user.should_see(marker="item-location", retries=30)
    assert marked(user, "item-location").value == bedroom["public_id"]
    set_marked_value(user, "item-location", shelf["public_id"])
    upload_file(user, "storage-camera.png", PNG, "image/png")
    await user.should_see("File uploaded successfully!", retries=30)
    user.find("Save Changes").click()
    await asyncio.sleep(0)
    await user.should_see("Item updated successfully.", retries=30)
    assert api.item(item_id).json()["item"]["location"] == "Storage Unit → Shelf A"

    await user.open(f"/edit-item/{item_id}")
    await user.should_see(marker="item-location", retries=30)
    assert marked(user, "item-location").value == shelf["public_id"]
    # A clearable select produces None; the item form must send an explicit clear.
    set_marked_value(user, "item-location", None)
    user.find("Save Changes").click()
    await asyncio.sleep(0)
    await user.should_see("Item updated successfully.", retries=30)
    detail = api.item(item_id).json()["item"]
    assert detail["location_id"] is None
    assert detail["name"] == "Camera"
    assert [row["original_filename"] for row in api.attachments(item_id)] == ["storage-camera.png"]
    await user.open(f"/item/{item_id}")
    await user.should_see("Item Information", retries=30)
    await user.should_not_see("Storage Unit → Shelf A")


async def test_renaming_parent_refreshes_selected_child_path_without_losing_edits(user: User, account, api) -> None:
    api.create_category("Electronics")
    home = create_location(api, "Home")
    basement = create_location(api, "Basement", home)
    item_id = api.add_phone(location=basement["public_id"])
    await sign_in(user, account)
    await user.open(f"/edit-item/{item_id}")
    await user.should_see(marker="item-location", retries=30)
    user.find("Item Name *").clear().type("Phone with new name")

    await open_manager(user)
    await user.should_see(marker=f"edit-location-{home['public_id']}", retries=30)
    user.find(marker=f"edit-location-{home['public_id']}").click()
    user.find(marker="location-name").clear().type("Family Home")
    user.find(marker="save-location").click()
    await user.should_see(kind=ui.label, content="Family Home → Basement", retries=30)
    user.find(marker="close-location-management").click()

    selector = marked(user, "item-location")
    assert selector.value == basement["public_id"]
    assert selector.options[basement["public_id"]] == "Family Home → Basement"
    assert next(iter(user.find("Item Name *").elements)).value == "Phone with new name"
    user.find("Save Changes").click()
    await user.should_see("Item updated successfully.", retries=30)
    detail = api.item(item_id).json()["item"]
    assert (detail["name"], detail["location_id"], detail["location"]) == (
        "Phone with new name", basement["public_id"], "Family Home → Basement",
    )


async def test_dialog_rejects_blank_and_case_insensitive_duplicate_names(user: User, account, api) -> None:
    api.create_category("Electronics")
    create_location(api, "Home")
    await open_add_item(user, account, api)
    fill_item(user, api, "Unsubmitted camera")
    await open_manager(user)

    user.find(marker="location-name").type("   ")
    user.find(marker="save-location").click()
    await user.should_see("Location name is required.", retries=30)
    user.find(marker="location-name").clear().type("  hOmE  ")
    user.find(marker="save-location").click()
    await user.should_see("A location with this name already exists here.", retries=30)

    assert marked(user, "location-management-dialog").value is True
    assert len(locations(api)) == 1
    assert next(iter(user.find("Item Name *").elements)).value == "Unsubmitted camera"
    assert api.get("/api/items/").json()["items"] == []


async def test_filter_uses_location_ids_for_equal_leaf_names_and_unassigned_items(user: User, account, api) -> None:
    api.create_category("Equipment")
    home = create_location(api, "Home")
    storage = create_location(api, "Storage Unit")
    home_shelf = create_location(api, "Shelf A", home)
    storage_shelf = create_location(api, "Shelf A", storage)
    unused = create_location(api, "Unused cupboard")
    api.add_phone(name="Home camera", location=home_shelf["public_id"])
    api.add_phone(name="Stored lamp", location=storage_shelf["public_id"])
    api.add_phone(name="Unplaced book")
    await sign_in(user, account)
    await user.open("/inventory")
    await user.should_see(marker="inventory-location-filter", retries=30)
    await wait_for_control(user, "inventory-location-filter")

    selector = marked(user, "inventory-location-filter")
    assert selector.options[home_shelf["public_id"]] == "Home → Shelf A"
    assert selector.options[storage_shelf["public_id"]] == "Storage Unit → Shelf A"
    assert unused["public_id"] not in selector.options  # Only assigned places are filters.
    for value, visible, hidden in (
        (home_shelf["public_id"], "Home camera", ["Stored lamp", "Unplaced book"]),
        (storage_shelf["public_id"], "Stored lamp", ["Home camera", "Unplaced book"]),
        ("unassigned", "Unplaced book", ["Home camera", "Stored lamp"]),
    ):
        set_marked_value(user, "inventory-location-filter", value)
        await user.should_see(kind=ui.link, content=visible, retries=30)
        for name in hidden:
            await user.should_not_see(kind=ui.link, content=name)
    set_marked_value(user, "inventory-location-filter", "all")
    for name in ("Home camera", "Stored lamp", "Unplaced book"):
        await user.should_see(kind=ui.link, content=name, retries=30)


async def test_switching_inventory_scopes_location_and_parent_choices(user: User, account, api) -> None:
    api.create_category("Equipment")
    first_inventory_id = api.inventory_id()
    first = create_location(api, "First inventory storage")
    response = api.post("/api/inventories/", json={"name": "Office"})
    assert response.status_code == 201, response.text
    second_inventory_id = response.json()["inventory"]["public_id"]
    api.create_category("Office equipment")
    second = create_location(api, "Office cupboard")
    other_api = type(api)(api.url)
    other_api.register(f"other_{uuid.uuid4().hex[:10]}")
    foreign = create_location(other_api, "Someone else's location")
    api.post("/api/inventories/select/", json={"inventory_id": first_inventory_id})
    await open_add_item(user, account, api)
    assert first["public_id"] in marked(user, "item-location").options
    assert second["public_id"] not in marked(user, "item-location").options

    # Use the actual inventory switcher, which leaves the old Add Item context.
    await user.should_see(kind=ui.select, content="Inventory", retries=30)
    with user:
        switcher = next(
            element for element in user.find(kind=ui.select).elements
            if element.props.get("label") == "Inventory"
        )
        switcher.value = second_inventory_id
    await user.should_see("Switched to Office", retries=50)
    await user.should_see(marker="inventory-location-filter", retries=50)
    await user.open(f"/add-item/{second_inventory_id}")
    await user.should_see(marker="item-location", retries=30)
    selector = marked(user, "item-location")
    assert second["public_id"] in selector.options
    assert first["public_id"] not in selector.options
    assert foreign["public_id"] not in selector.options
    await open_manager(user)
    await user.should_see(marker=f"location-{second['public_id']}", retries=30)
    parents = marked(user, "location-parent").options
    assert second["public_id"] in parents
    assert first["public_id"] not in parents
    assert foreign["public_id"] not in parents
    await user.should_not_see(marker=f"location-{first['public_id']}")
    await user.should_not_see(marker=f"location-{foreign['public_id']}")


async def test_archiving_unused_location_removes_it_from_item_choices(user: User, account, api) -> None:
    api.create_category("Equipment")
    unused = create_location(api, "Old storage unit")
    await open_add_item(user, account, api)
    set_marked_value(user, "item-location", unused["public_id"])
    await open_manager(user)
    await user.should_see(marker=f"archive-location-{unused['public_id']}", retries=30)
    user.find(marker=f"archive-location-{unused['public_id']}").click()
    await user.should_see(marker="confirm-location-archive", retries=30)
    user.find(marker="confirm-location-archive").click()
    await user.should_see("Location archived.", retries=30)
    await user.should_not_see(marker=f"location-{unused['public_id']}", retries=50)
    await wait_for_control(user, "item-location")
    user.find(marker="close-location-management").click()

    assert unused["public_id"] not in marked(user, "item-location").options
    assert marked(user, "item-location").value in (None, "")
    assert locations(api) == []


async def test_manager_prevents_cycles_and_explains_archive_guards(user: User, account, api) -> None:
    api.create_category("Equipment")
    home = create_location(api, "Home")
    basement = create_location(api, "Basement", home)
    item_id = api.add_phone(name="Basement radio", location=basement["public_id"])
    await open_add_item(user, account, api)
    await open_manager(user)

    user.find(marker=f"edit-location-{home['public_id']}").click()
    parents = marked(user, "location-parent").options
    assert home["public_id"] not in parents
    assert basement["public_id"] not in parents
    user.find(marker="cancel-location-edit").click()

    for location, message in (
        (home, "Move or archive this location's child locations before archiving it."),
        (basement, "Move or unassign the items in this location before archiving it."),
    ):
        user.find(marker=f"archive-location-{location['public_id']}").click()
        assert marked(user, "archive-location-dialog").value is True
        user.find(marker="confirm-location-archive").click()
        await user.should_see(message, retries=30)
        assert marked(user, "archive-location-dialog").value is True
        user.find(marker="cancel-location-archive").click()

    assert {row["public_id"] for row in locations(api)} == {home["public_id"], basement["public_id"]}
    assert api.item(item_id).json()["item"]["location_id"] == basement["public_id"]


async def test_stale_archived_selection_cannot_create_an_item(user: User, account, api) -> None:
    api.create_category("Equipment")
    stale = create_location(api, "Temporary storage")
    await open_add_item(user, account, api)
    fill_item(user, api, "Unsaved drill")
    set_marked_value(user, "item-location", stale["public_id"])
    response = archive_location(api, stale)
    assert response.ok, response.text
    user.find(kind=ui.button, content="Add Item").click()

    await user.should_see("Couldn't add the item. Check the highlighted fields.", retries=30)
    assert api.get("/api/items/").json()["items"] == []
    assert next(iter(user.find("Item Name *").elements)).value == "Unsaved drill"


async def test_dialog_load_failure_has_a_working_retry(user: User, account, api, monkeypatch) -> None:
    from utilities import location_management

    api.create_category("Equipment")
    location = create_location(api, "Back room")
    await open_add_item(user, account, api)
    real_request = location_management._location_request

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("test backend unavailable")

    monkeypatch.setattr(location_management, "_location_request", unavailable)
    user.find(marker="manage-locations").click()
    await user.should_see(marker="retry-location-management", retries=30)
    monkeypatch.setattr(location_management, "_location_request", real_request)
    user.find(marker="retry-location-management").click()
    await user.should_see(marker=f"location-{location['public_id']}", retries=30)


async def test_location_dialog_expired_session_returns_to_login(user: User, account, api) -> None:
    api.create_category("Equipment")
    await open_add_item(user, account, api)
    stored = next(iter(app.storage._users.values()))  # pylint: disable=protected-access
    api.session.cookies.clear()
    api.session.cookies.set("sessionid", stored["auth_cookies"]["sessionid"])
    assert api.post("/api/auth/logout/").ok

    user.find(marker="manage-locations").click()
    await user.should_see("Your session expired. Please sign in again.", retries=30)
    await user.should_see("Sign in to your account", retries=30)
