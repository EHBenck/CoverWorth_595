"""Sprint 7 regression: location filters survive inventory presentation changes.

These interactions use the real Django API and a disposable test database.
The complete create/assign/edit/archive workflow is covered in test_locations.
"""

from nicegui import ui
from nicegui.testing import User

from tests.test_locations import (
    archive_location,
    create_location,
    marked,
    open_manager,
    set_marked_value,
    wait_for_control,
    wait_for_exact_label,
)
from tests.ui_helpers import click_icon_button, click_menu_item, sign_in


async def test_location_filter_preserves_uuid_and_archived_state_across_views(
    user: User, account, api,
) -> None:
    api.create_category("Equipment")
    home = create_location(api, "Home")
    storage = create_location(api, "Storage Unit")
    basement = create_location(api, "Basement", home)
    shelf = create_location(api, "Shelf 2", storage)
    active_id = api.add_phone(name="Basement camera", location=basement["public_id"])
    api.add_phone(name="Storage camera", location=shelf["public_id"])
    archived_id = api.add_phone(name="Archived camera", location=basement["public_id"])
    response = api.post(f"/api/item/{archived_id}/archive/")
    assert response.status_code == 200, response.text

    await sign_in(user, account)
    await user.open("/inventory")
    await user.should_see(marker="inventory-location-filter", retries=30)
    await wait_for_control(user, "inventory-location-filter")
    set_marked_value(user, "inventory-location-filter", basement["public_id"])
    await user.should_see(kind=ui.link, content="Basement camera", retries=30)
    await user.should_not_see(kind=ui.link, content="Storage camera")

    for icon in ("grid_view", "view_list"):
        click_icon_button(user, icon)
        await user.should_see(kind=ui.link, content="Basement camera", retries=30)
        await user.should_not_see(kind=ui.link, content="Storage camera")
        assert marked(user, "inventory-location-filter").value == basement["public_id"]
        assert marked(user, f"item-location-{active_id}").text == "Home → Basement"

    with user:
        next(iter(user.find(kind=ui.toggle).elements)).value = "archived"
    await user.should_see(kind=ui.link, content="Archived camera", retries=30)
    await user.should_not_see(kind=ui.link, content="Basement camera")
    for icon in ("grid_view", "view_list"):
        click_icon_button(user, icon)
        await user.should_see(kind=ui.link, content="Archived camera", retries=30)
        await user.should_not_see(kind=ui.link, content="Basement camera")
        assert marked(user, "inventory-location-filter").value == basement["public_id"]

    # A location rename refreshes inventory rows. It must keep the selected UUID
    # and the archived item scope, including when the selected place is a child.
    await open_manager(user)
    user.find(marker=f"edit-location-{home['public_id']}").click()
    user.find(marker="location-name").clear().type("Family Home")
    user.find(marker="save-location").click()
    await wait_for_exact_label(user, "Family Home → Basement")
    await wait_for_control(user, "location-name")
    user.find(marker="close-location-management").click()
    await user.should_see(kind=ui.link, content="Archived camera", retries=30)
    await user.should_not_see(kind=ui.link, content="Basement camera")
    selector = marked(user, "inventory-location-filter")
    assert selector.value == basement["public_id"]
    assert selector.options[basement["public_id"]] == "Family Home → Basement"
    assert marked(user, f"item-location-{archived_id}").text == "Family Home → Basement"

    with user:
        next(iter(user.find(kind=ui.toggle).elements)).value = "active"
    await user.should_see(kind=ui.link, content="Basement camera", retries=30)
    await user.should_not_see(kind=ui.link, content="Storage camera")
    await user.should_not_see(kind=ui.link, content="Archived camera")
    assert marked(user, "inventory-location-filter").value == basement["public_id"]
    assert api.item(active_id).json()["item"]["location"] == "Family Home → Basement"


async def test_archived_location_restore_error_can_be_resolved_in_item_editor(
    user: User, account, api,
) -> None:
    api.create_category("Equipment")
    old_location = create_location(api, "Old storage")
    item_id = api.add_phone(name="Archived camera", location=old_location["public_id"])
    assert api.post(f"/api/item/{item_id}/archive/").ok
    response = archive_location(api, old_location)
    assert response.status_code == 200, response.text

    await sign_in(user, account)
    await user.open("/inventory")
    await user.should_see(marker="inventory-location-filter", retries=30)
    with user:
        next(iter(user.find(kind=ui.toggle).elements)).value = "archived"
    await user.should_see(kind=ui.link, content="Archived camera", retries=30)
    click_menu_item(user, "Restore")
    await user.should_see(
        "Choose an active location in this inventory or unassign the item before restoring it.",
        retries=30,
    )
    assert api.get("/api/items/").json()["items"] == []

    # Archived items can be edited without restoring them. Clearing the stale
    # location is the recovery offered by the restore error above.
    await user.open(f"/edit-item/{item_id}")
    await user.should_see(marker="item-location", retries=30)
    set_marked_value(user, "item-location", None)
    user.find("Save Changes").click()
    await user.should_see("Item updated successfully.", retries=30)
    assert api.item(item_id).json()["item"]["location_id"] is None
    assert api.get("/api/items/").json()["items"] == []

    await user.open("/inventory")
    await user.should_see(marker="inventory-location-filter", retries=30)
    with user:
        next(iter(user.find(kind=ui.toggle).elements)).value = "archived"
    await user.should_see(kind=ui.link, content="Archived camera", retries=30)
    click_menu_item(user, "Restore")
    await user.should_see("'Archived camera' restored.", retries=30)
    with user:
        next(iter(user.find(kind=ui.toggle).elements)).value = "active"
    await user.should_see(kind=ui.link, content="Archived camera", retries=30)
    assert marked(user, f"item-location-{item_id}").text == "Unassigned"
    assert [item["public_id"] for item in api.get("/api/items/").json()["items"]] == [item_id]
