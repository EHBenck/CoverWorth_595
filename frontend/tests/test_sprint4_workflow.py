"""
Sprint 4 integration pass, driven through the real NiceGUI pages.

Register -> Login -> Create/Switch Inventory -> Add Item -> Upload Attachment
-> View Item -> Edit Item -> Run Valuation -> Accept Valuation -> Archive Item

The live Django server answers eBay calls from tests/fake_ebay.py, so no
test reaches the real eBay API. "View History" has no page or endpoint yet,
so it is not covered here.
"""

import asyncio
import uuid

import pytest
from nicegui import ui
from nicegui.testing import User

from tests import app_under_test
from tests.conftest import PASSWORD
from tests.fake_ebay import EBAY_DOWN
from tests.ui_helpers import (
    click_button,
    click_icon_button,
    click_menu_item,
    open_login,
    set_value,
    sign_in,
    upload_file,
)

pytestmark = pytest.mark.module_under_test(app_under_test)

JPEG = b"\xff\xd8\xff fake jpeg"
PDF = b"%PDF-1.4 fake"


def images(user: User) -> list[str]:
    with user:
        return [image.source for image in user.find(kind=ui.image).elements]


# ------------------------------------------------------------
# PRIMARY WORKFLOW
# ------------------------------------------------------------

async def test_primary_workflow_through_the_pages(user: User, api) -> None:
    username = f"flow_{uuid.uuid4().hex[:8]}"

    # Register (lands on the dashboard, signed in)
    await open_login(user)
    user.find("Register").click()
    await user.should_see("Create your account", retries=20)
    for label, value in {
        "First name": "Ada",
        "Last name": "Lovelace",
        "Email": f"{username}@example.com",
        "Username": username,
        "Password": PASSWORD,
        "Confirm password": PASSWORD,
    }.items():
        user.find(label).type(value)
    user.find("Create account").click()
    await user.should_see("Recent Items", retries=20)

    # Sign out and Login again
    user.find("Sign out").click()
    await user.should_see("Sign in to your account", retries=20)
    await sign_in(user, {"username": username, "password": PASSWORD})
    api.post("/api/auth/login/", json={"username": username, "password": PASSWORD})

    # Create Inventory from the header
    await user.should_see("New", retries=20)
    user.find(kind=ui.button, content="New").click()
    user.find("Inventory name").type("Garage")
    click_button(user, "Create")
    await user.should_see("Created inventory: Garage", retries=20)

    inventories = api.get("/api/inventories/").json()["inventories"]
    garage_id = next(inv["public_id"] for inv in inventories if inv["name"] == "Garage")
    api.post("/api/inventories/select/", json={"inventory_id": garage_id})
    api.create_category("Phones")

    # Add Item with a photo
    await user.open(f"/add-item/{garage_id}")
    await user.should_see("Add a new belonging to Garage", retries=20)
    user.find("Item Name *").type("iPhone 13")
    user.find("Category *").click()
    user.find("Phones").click()
    set_value(user, "Date Acquired *", "2025-09-01")
    set_value(user, "Purchase Price ($) *", 799)
    upload_file(user, "phone.jpg", JPEG, "image/jpeg")
    await user.should_see("Photo 'phone.jpg' selected.", retries=20)
    user.find(kind=ui.button, content="Add Item").click()
    await user.should_see("Item added successfully.", retries=20)

    item = api.get("/api/items/").json()["items"][0]
    item_id = item["public_id"]
    assert (item["name"], item["inventory"], item["category"]) == ("iPhone 13", "Garage", "Phones")
    assert [(a["original_filename"], a["is_primary"]) for a in api.attachments(item_id)] == [
        ("phone.jpg", True)
    ]

    # View Item from the inventory list
    await user.open("/inventory")
    await user.should_see(kind=ui.link, content="iPhone 13", retries=20)
    assert any("/media/item_attachments/" in source for source in images(user))
    user.find(kind=ui.link, content="iPhone 13").click()
    await user.should_see("Item Information", retries=20)
    await user.should_see("Phones")
    await user.should_see("$799.00")

    # Edit Item and upload a receipt
    user.find(kind=ui.button, content="Edit Item").click()
    await user.should_see("Update the details for iPhone 13.", retries=20)
    await user.should_see("phone.jpg", retries=20)
    upload_file(user, "receipt.pdf", PDF, "application/pdf")
    await user.should_see("File uploaded successfully!", retries=20)
    await user.should_see("receipt.pdf", retries=20)
    user.find("Item Name *").clear().type("iPhone 13 Blue")
    user.find("Save Changes").click()
    await user.should_see("Item updated successfully.", retries=20)

    assert api.item(item_id).json()["item"]["name"] == "iPhone 13 Blue"
    assert sorted((a["original_filename"], a["file_type"]) for a in api.attachments(item_id)) == [
        ("phone.jpg", "photo"),
        ("receipt.pdf", "receipt"),
    ]

    # Run Valuation and Accept it
    await user.open("/valuations")
    await user.should_see("iPhone 13 Blue", retries=20)
    click_button(user, "Update")
    await user.should_see("Live estimate: $247.00", retries=20)
    click_button(user, "Accept $247.00")
    await user.should_see("Valuation saved: $247.00", retries=20)

    detail = api.item(item_id).json()["item"]
    assert detail["current_estimated_amount"] == "247.00"
    assert detail["valuation_date"] is not None

    await user.open(f"/item/{item_id}")
    await user.should_see("Last valued", retries=20)

    # Archive Item from the inventory menu
    await user.open("/inventory")
    await user.should_see(kind=ui.link, content="iPhone 13 Blue", retries=20)
    # The page reloads its rows once more right after it opens (ui.timer in
    # inventory.py); a dialog opened before that is rebuilt away.
    await asyncio.sleep(1)
    click_icon_button(user, "more_vert")
    click_menu_item(user, "Delete")
    await user.should_see("Are you sure you want to delete 'iPhone 13 Blue'?", retries=20)
    click_button(user, "Delete")
    await user.should_see("Item 'iPhone 13 Blue' deleted successfully.", retries=20)

    assert api.item(item_id).status_code == 404
    assert api.get("/api/items/").json()["items"] == []


# ------------------------------------------------------------
# INVENTORIES: SWITCHING / EMPTY / ISOLATION
# ------------------------------------------------------------

async def test_switching_inventory_changes_what_the_pages_show(user: User, account, api) -> None:
    api.create_category("Phones")
    api.add_phone()
    api.post("/api/inventories/", json={"name": "Storage Unit"})

    await sign_in(user, account)
    await user.should_see("iPhone 13", retries=20)

    await user.should_see(kind=ui.select, retries=20)
    user.find(kind=ui.select).click()
    user.find("Storage Unit").click()
    await user.should_see("Switched to Storage Unit", retries=20)

    await user.open("/dashboard")
    await user.should_see("Recent Items", retries=20)
    await user.should_not_see("iPhone 13")

    await user.open("/inventory")
    await user.should_see("No items found", retries=20)


async def test_empty_inventory_pages(user: User, account) -> None:
    await sign_in(user, account)

    await user.open("/inventory")
    await user.should_see("No items found", retries=20)

    await user.open("/valuations")
    await user.should_see("No valuations found", retries=20)
    await user.should_see("No valuation available")

    await user.open("/categories")
    await user.should_see("No categories found", retries=20)


async def test_user_cannot_open_another_users_item(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    api.upload(item_id, "phone.jpg", JPEG, "image/jpeg")

    intruder = api.__class__(api.url)
    intruder_account = {"username": f"other_{uuid.uuid4().hex[:8]}", "password": PASSWORD}
    intruder.register(intruder_account["username"])

    await sign_in(user, intruder_account)
    await user.should_not_see("iPhone 13")

    await user.open(f"/item/{item_id}")
    await user.should_see("Item not found", retries=20)
    await user.should_not_see("iPhone 13")

    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Item not found", retries=20)

    await user.open("/valuations")
    await user.should_see("No valuations found", retries=20)


# ------------------------------------------------------------
# INVALID / ARCHIVED ITEM IDS
# ------------------------------------------------------------

@pytest.mark.parametrize("item_id", [str(uuid.uuid4()), "not-a-uuid", "None"])
@pytest.mark.parametrize("page", ["/item", "/edit-item"])
async def test_invalid_item_ids_show_not_found(user: User, account, page: str, item_id: str) -> None:
    await sign_in(user, account)

    await user.open(f"{page}/{item_id}")

    await user.should_see("Item not found", retries=20)


async def test_archived_item_shows_not_found(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    response = api.session.delete(
        f"{api.url}/api/item/{item_id}/edit/", headers=api._headers(), timeout=5,
    )
    assert response.ok, response.text
    await sign_in(user, account)

    for page in ("/item", "/edit-item"):
        await user.open(f"{page}/{item_id}")
        await user.should_see("Item not found", retries=20)


# ------------------------------------------------------------
# ATTACHMENTS
# ------------------------------------------------------------

async def test_attachment_can_be_removed_on_the_edit_page(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    api.upload(item_id, "phone.jpg", JPEG, "image/jpeg")
    await sign_in(user, account)

    await user.open(f"/edit-item/{item_id}")
    await user.should_see("phone.jpg", retries=20)
    click_icon_button(user, "delete")

    await user.should_see("Attachment deleted.", retries=20)
    await user.should_see("No attachments yet", retries=20)
    assert api.attachments(item_id) == []


async def test_primary_photo_shows_on_dashboard_and_inventory(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    photo_url = api.upload(item_id, "phone.jpg", JPEG, "image/jpeg")["file_url"]

    await sign_in(user, account)
    assert any(source.endswith(photo_url) for source in images(user))

    await user.open("/inventory")
    await user.should_see(kind=ui.link, content="iPhone 13", retries=20)
    assert any(source.endswith(photo_url) for source in images(user))


# ------------------------------------------------------------
# VALUATION ERRORS
# ------------------------------------------------------------

async def test_ebay_failure_shows_a_useful_error(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone(name=f"iPhone 13 {EBAY_DOWN}")
    await sign_in(user, account)

    await user.open("/valuations")
    await user.should_see(f"iPhone 13 {EBAY_DOWN}", retries=20)
    click_button(user, "Update")

    await user.should_see("Valuation request failed: Unable to retrieve eBay listings", retries=20)
    await user.should_see("No valuation available")
    assert api.item(item_id).json()["item"]["current_estimated_amount"] is None


async def test_accept_without_a_valuation_warns(user: User, account, api) -> None:
    api.create_category("Phones")
    api.add_phone()
    await sign_in(user, account)

    await user.open("/valuations")
    await user.should_see("iPhone 13", retries=20)
    click_button(user, "No valuation available")

    await user.should_see("Please update an item's valuation first.", retries=20)


async def test_backend_down_during_valuation_does_not_crash(user: User, account, api, monkeypatch) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    await sign_in(user, account)

    await user.open("/valuations")
    await user.should_see("iPhone 13", retries=20)
    click_button(user, "Update")
    await user.should_see("Live estimate: $247.00", retries=20)

    from pages import valuations
    monkeypatch.setattr(valuations, "BACKEND_URL", "http://127.0.0.1:9")
    monkeypatch.setattr("backend_client.BACKEND_URL", "http://127.0.0.1:9")

    click_button(user, "Update")
    await user.should_see("Could not connect to the backend.", retries=50)

    click_button(user, "Accept $247.00")
    await user.should_see("Could not save valuation", retries=50)
    await user.should_see("Valuations")
    assert api.item(item_id).json()["item"]["current_estimated_amount"] is None
