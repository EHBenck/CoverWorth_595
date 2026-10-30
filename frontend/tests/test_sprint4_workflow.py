"""
Sprint 4 integration pass, driven through the real NiceGUI pages.

Register -> Login -> Create/Switch Inventory -> Add Item -> Upload Attachment
-> View Item -> Edit Item -> Run Valuation -> Accept Valuation -> Archive Item

The live Django server answers eBay calls from tests/fake_ebay.py, so no
test reaches the real eBay API. "View History" has no page or endpoint yet,
so it is not covered here.
"""

import asyncio
import base64
from datetime import datetime
import uuid

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

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
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


def receipt_pdf() -> bytes:
    """A complete one-page PDF, including its cross-reference table."""
    content = b"BT /F1 12 Tf 30 100 Td (Test receipt) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 150] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


PDF = receipt_pdf()


def images(user: User) -> list[str]:
    with user:
        return [element.source for element in user.client.elements.values() if isinstance(element, ui.image)]


def inventory_filter(user: User, default_option: str):
    with user:
        return next(
            element for element in user.find(kind=ui.select).elements
            if default_option in element.options
        )


# ------------------------------------------------------------
# PRIMARY WORKFLOW
# ------------------------------------------------------------

@pytest.mark.parametrize("run_valuation", [False, True], ids=["inventory_only", "with_valuation"])
async def test_primary_workflow_through_the_pages(user: User, api, run_valuation: bool) -> None:
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
    assert any(source.startswith("/attachments/") for source in images(user))
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

    # Keep the optional valuation journey separate from inventory-only coverage.
    if run_valuation:
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
    attachment = api.upload(item_id, "phone.jpg", JPEG, "image/jpeg")
    photo_url = f"/attachments/{attachment['public_id']}"

    await sign_in(user, account)
    assert photo_url in images(user)

    await user.open("/inventory")
    await user.should_see(kind=ui.link, content="iPhone 13", retries=20)
    assert photo_url in images(user)


# ------------------------------------------------------------
# CATEGORY CONTEXT / EXACT RECENCY / ITEM FORM REGRESSIONS
# ------------------------------------------------------------

async def test_category_view_items_opens_inventory_with_that_filter(user: User, account, api) -> None:
    for category_name in ("Home & Office", "Furniture"):
        api.create_category(category_name)
    categories = api.get(f"/api/inventory/{api.inventory_id()}/add-item/").json()["categories"]
    category_ids = {category["name"]: category["id"] for category in categories}
    api.add_phone(name="Office camera", category=category_ids["Home & Office"])
    api.add_phone(name="Living room chair", category=category_ids["Furniture"])
    await sign_in(user, account)
    await user.open("/categories")
    await user.should_see("Home & Office", retries=20)

    with user:
        card = next(
            element for element in user.client.elements.values()
            if isinstance(element, ui.card) and "category-card" in element.classes
            and any(getattr(child, "text", None) == "Home & Office" for child in element.descendants())
        )
        button = next(
            child for child in card.descendants()
            if isinstance(child, ui.button) and child.text == "View Items"
        )
    UserInteraction(user, {button}, "View Items").click()

    await user.should_see(kind=ui.link, content="Office camera", retries=20)
    await user.should_not_see(kind=ui.link, content="Living room chair")
    assert inventory_filter(user, "All Categories").value == "Home & Office"
    with user:
        inventory_filter(user, "All Categories").value = "All Categories"
    await user.should_see(kind=ui.link, content="Living room chair", retries=20)


async def test_unknown_category_query_keeps_inventory_usable(user: User, account, api) -> None:
    api.create_category("Phones")
    api.add_phone()
    await sign_in(user, account)
    await user.open("/inventory?category=Category%20that%20no%20longer%20exists")
    await user.should_see(kind=ui.link, content="iPhone 13", retries=20)
    assert inventory_filter(user, "All Categories").value == "All Categories"


async def test_recently_updated_orders_categories_within_the_same_day(user: User, account, api, seed_backend) -> None:
    older = api.create_category("Alpha")
    newer = api.create_category("Zebra")
    seed_backend(f"""
        from datetime import datetime, timezone
        from myapp.models import Category
        Category.objects.filter(public_id={older['public_id']!r}).update(
            updated_at=datetime(2026, 1, 8, 9, 0, tzinfo=timezone.utc))
        Category.objects.filter(public_id={newer['public_id']!r}).update(
            updated_at=datetime(2026, 1, 8, 9, 1, tzinfo=timezone.utc))
    """)
    rows = api.get(f"/api/inventory/{api.inventory_id()}/categories/").json()["categories"]
    expected = [
        row["name"] for row in sorted(
            rows, key=lambda row: datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            reverse=True,
        )
    ]
    assert expected == ["Zebra", "Alpha"]
    await sign_in(user, account)
    await user.open("/categories")
    await user.should_see("Zebra", retries=20)
    with user:
        inventory_filter(user, "Recently Updated").value = "Recently Updated"
        labels = sorted(
            (element for element in user.client.elements.values()
             if isinstance(element, ui.label) and "category-name" in element.classes),
            key=lambda element: element.id,
        )
    assert [label.text for label in labels] == expected


@pytest.mark.parametrize("quantity", [0, -1, 1.5, None], ids=["zero", "negative", "fraction", "blank"])
async def test_add_item_rejects_invalid_quantity_without_saving(user: User, account, api, quantity) -> None:
    api.create_category("Phones")
    await sign_in(user, account)
    await user.open(f"/add-item/{api.inventory_id()}")
    await user.should_see("Item Name *", retries=20)
    user.find("Item Name *").type("Do not save this item")
    user.find("Category *").click()
    user.find("Phones").click()
    set_value(user, "Date Acquired *", "2025-09-01")
    set_value(user, "Purchase Price ($) *", 20)
    set_value(user, "Quantity", quantity)
    click_button(user, "Add Item")

    await user.should_see("Quantity must be a whole number of at least 1.", retries=20)
    assert api.get("/api/items/").json()["items"] == []


@pytest.mark.parametrize("quantity", [0, -1, 1.5, None], ids=["zero", "negative", "fraction", "blank"])
async def test_edit_item_rejects_invalid_quantity_without_saving(user: User, account, api, quantity) -> None:
    api.create_category("Phones")
    item_id = api.add_phone(name="Original name", quantity="3")
    await sign_in(user, account)
    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Update the details for Original name.", retries=20)
    await user.should_see("Save Changes", retries=20)
    user.find("Item Name *").clear().type("Do not save this edit")
    set_value(user, "Quantity", quantity)
    click_button(user, "Save Changes")

    await user.should_see("Quantity must be a whole number of at least 1.", retries=20)
    saved = api.item(item_id).json()["item"]
    assert (saved["name"], saved["quantity"]) == ("Original name", 3)


async def test_edit_item_displays_and_preserves_explicit_zero_values(user: User, account, api) -> None:
    api.create_category("Phones")
    item_id = api.add_phone(name="Gift", purchase_amount="0.00", manual_value="0.00")
    await sign_in(user, account)
    await user.open(f"/edit-item/{item_id}")
    await user.should_see("Update the details for Gift.", retries=20)
    await user.should_see("Save Changes", retries=20)
    with user:
        for label in ("Purchase Price ($) *", "Manual Value ($)"):
            assert next(iter(user.find(label).elements)).value == 0
    user.find("Item Name *").clear().type("Gift kept at home")
    click_button(user, "Save Changes")
    await user.should_see("Item updated successfully.", retries=20)
    saved = api.item(item_id).json()["item"]
    assert saved["name"] == "Gift kept at home"
    assert saved["purchase_amount"] == "0.00"
    assert saved["manual_value"] == "0.00"


async def test_inventory_location_filter_uses_persisted_locations(user: User, account, api, seed_backend) -> None:
    api.create_category("Equipment")
    office_id = api.add_phone(name="Office camera")
    attic_id = api.add_phone(name="Attic lamp")
    seed_backend(f"""
        from django.db import transaction
        from myapp.models import Item, Location
        with transaction.atomic():
            for item_id, location_name in {[(office_id, 'Office'), (attic_id, 'Attic')]!r}:
                item = Item.objects.get(public_id=item_id, inventory__owner__username={account['username']!r})
                location = Location.objects.create(inventory=item.inventory, name=location_name)
                item.location = location
                item.save(update_fields=['location', 'updated_at'])
    """)
    await sign_in(user, account)
    await user.open("/inventory")
    await user.should_see(kind=ui.link, content="Office camera", retries=20)
    await user.should_see(kind=ui.link, content="Attic lamp", retries=20)
    # Locations are identified by UUID, so equal names under different parents
    # cannot accidentally match the same filter option.
    selector = next(iter(user.find(marker="inventory-location-filter").elements))
    office_location = api.item(office_id).json()["item"]["location_id"]
    attic_location = api.item(attic_id).json()["item"]["location_id"]
    assert selector.options == {
        "all": "All Locations",
        "unassigned": "Unassigned",
        office_location: "Office",
        attic_location: "Attic",
    }
    with user:
        selector.value = office_location
    await user.should_see(kind=ui.link, content="Office camera", retries=20)
    await user.should_not_see(kind=ui.link, content="Attic lamp")
    with user:
        selector.value = attic_location
    await user.should_see(kind=ui.link, content="Attic lamp", retries=20)
    await user.should_not_see(kind=ui.link, content="Office camera")
    with user:
        selector.value = "all"
    await user.should_see(kind=ui.link, content="Office camera", retries=20)
    await user.should_see(kind=ui.link, content="Attic lamp", retries=20)


# ------------------------------------------------------------
# PRIVATE ATTACHMENT NAVIGATION / FILE DELIVERY
# ------------------------------------------------------------

@pytest.mark.parametrize("failure", ["stream", "send"])
async def test_attachment_stream_releases_upstream_on_failure(failure) -> None:
    from utilities.attachments import _AttachmentResponse

    closed = []

    async def content():
        if failure == "stream":
            raise RuntimeError("stream failed")
        yield b"attachment data"

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        if failure == "send" and message["type"] == "http.response.body":
            raise RuntimeError("send failed")

    response = _AttachmentResponse(content(), headers={}, close=lambda: closed.append(True))
    with pytest.raises(RuntimeError, match=f"{failure} failed"):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert closed == [True]


@pytest.mark.parametrize("filename,content,content_type,file_type", [
    ("photo.png", PNG, "image/png", "photo"),
    ("receipt.pdf", PDF, "application/pdf", "receipt"),
])
async def test_attachment_eye_opens_readable_owner_file(
    user: User, account, api, monkeypatch, filename, content, content_type, file_type,
) -> None:
    api.create_category("Phones")
    item_id = api.add_phone()
    attachment = api.upload(item_id, filename, content, content_type, file_type)
    await sign_in(user, account)
    await user.open(f"/edit-item/{item_id}")
    await user.should_see(filename, retries=20)

    opened = []
    monkeypatch.setattr(ui.navigate, "to", lambda target, *, new_tab=False: opened.append((target, new_tab)))
    click_icon_button(user, "visibility")
    path = f"/attachments/{attachment['public_id']}"
    assert opened == [(path, True)]

    response = await user.http_client.get(path)
    assert response.status_code == 200, response.text
    assert response.content == content
    assert response.headers["content-type"].split(";")[0] == content_type
    assert "no-store" in response.headers["cache-control"]
    head = await user.http_client.head(path)
    assert head.status_code == 200
    assert head.content == b""
    assert int(head.headers["content-length"]) == len(content)


async def test_pdf_only_item_uses_dashboard_icon_instead_of_receipt_thumbnail(user: User, account, api) -> None:
    api.create_category("Equipment")
    item_id = api.add_phone(name="Receipt-only item")
    attachment = api.upload(item_id, "receipt.pdf", PDF, "application/pdf", "receipt")
    await sign_in(user, account)
    await user.should_see(kind=ui.link, content="Receipt-only item", retries=20)
    assert f"/attachments/{attachment['public_id']}" not in images(user)
    with user:
        row = next(
            element for element in user.client.elements.values()
            if "recent-item" in element.classes
            and any(getattr(child, "text", None) == "Receipt-only item" for child in element.descendants())
        )
        assert not any(isinstance(child, ui.image) for child in row.descendants())
        assert any(isinstance(child, ui.icon) for child in row.descendants())


async def test_private_attachment_denies_anonymous_and_other_users(user: User, account, api) -> None:
    api.create_category("Phones")
    attachment = api.upload(api.add_phone(), "private.png", PNG, "image/png")
    path = f"/attachments/{attachment['public_id']}"
    await open_login(user)
    assert (await user.http_client.get(path)).status_code == 401

    other_api = type(api)(api.url)
    other_account = {"username": f"other_{uuid.uuid4().hex[:8]}", "password": PASSWORD}
    other_api.register(other_account["username"])
    await sign_in(user, other_account)
    response = await user.http_client.get(path)
    assert response.status_code == 404
    assert response.content != PNG


@pytest.mark.parametrize("archive_target", ["attachment", "item", "inventory"])
async def test_private_attachment_stops_serving_after_archive(user: User, account, api, archive_target) -> None:
    api.create_category("Phones")
    inventory_id = api.inventory_id()
    item_id = api.add_phone()
    attachment = api.upload(item_id, "private.png", PNG, "image/png")
    path = f"/attachments/{attachment['public_id']}"
    await sign_in(user, account)
    assert (await user.http_client.get(path)).content == PNG

    if archive_target == "inventory":
        created = api.post("/api/inventories/", json={"name": "Replacement"})
        assert created.status_code == 201, created.text
        response = api.post(f"/api/inventories/{inventory_id}/archive/", json={})
    else:
        endpoint = (
            f"/api/attachment/{attachment['public_id']}/"
            if archive_target == "attachment" else f"/api/item/{item_id}/edit/"
        )
        response = api.session.delete(f"{api.url}{endpoint}", headers=api._headers(), timeout=5)
    assert response.status_code == 200, response.text
    denied = await user.http_client.get(path)
    assert denied.status_code == 404
    assert denied.content != PNG


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
