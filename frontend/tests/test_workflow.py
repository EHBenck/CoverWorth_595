"""
Sprint 3 integration pass, driven through the real NiceGUI pages.
Kept as the regression suite for Sprint 4 (see test_sprint4_workflow.py).

Login -> Dashboard -> Inventory -> Add Item -> View/Edit Item

Every test talks to a live Django server (see conftest.py). "/" is the login
page; the dashboard lives at "/dashboard".
"""

import uuid

import pytest
from nicegui import app, ui
from nicegui.testing import User

from tests import app_under_test
from tests.ui_helpers import make_backend_unreachable, open_login, set_value, sign_in

pytestmark = pytest.mark.module_under_test(app_under_test)

PROTECTED_PATHS = [
    "/dashboard",
    "/inventory",
    "/categories",
    "/valuations",
    "/reports",
    "/settings",
    f"/add-item/{uuid.uuid4()}",
    f"/edit-item/{uuid.uuid4()}",
    f"/item/{uuid.uuid4()}",
]


# ------------------------------------------------------------
# REGISTER / LOGIN / LOGOUT
# ------------------------------------------------------------

async def test_register_from_login_page_lands_on_empty_dashboard(user: User, api) -> None:
    username = f"new_{uuid.uuid4().hex[:8]}"

    await open_login(user)
    user.find("Register").click()
    await user.should_see("Create your account", retries=20)

    user.find("First name").type("Ada")
    user.find("Last name").type("Lovelace")
    user.find("Email").type(f"{username}@example.com")
    user.find("Username").type(username)
    user.find("Password").type("Sturdy-passphrase-42")
    user.find("Confirm password").type("Sturdy-passphrase-42")
    user.find("Create account").click()

    await user.should_see("Recent Items", retries=20)
    await user.should_see(username)
    api.post("/api/auth/login/", json={"username": username, "password": "Sturdy-passphrase-42"})
    assert api.get("/api/dashboard/").json()["summary"]["total_items"] == 0


async def test_register_shows_backend_validation_errors(user: User, account) -> None:
    await user.open("/register")
    user.find("First name").type("Ada")
    user.find("Last name").type("Lovelace")
    user.find("Email").type("not-an-email")
    user.find("Username").type(account["username"])
    user.find("Password").type("Sturdy-passphrase-42")
    user.find("Confirm password").type("Sturdy-passphrase-42")
    user.find("Create account").click()

    await user.should_see("This username is already taken.", retries=20)
    await user.should_see("Enter a valid email address.")
    await user.should_not_see("Recent Items")


async def test_register_rejects_mismatched_passwords_before_calling_backend(user: User) -> None:
    await user.open("/register")
    user.find("Password").type("Sturdy-passphrase-42")
    user.find("Confirm password").type("Different-passphrase-42")
    user.find("Create account").click()

    await user.should_see("Passwords do not match.")


async def test_register_shows_password_requirements_while_typing(user: User) -> None:
    await user.open("/register")
    await user.should_see("Your password must be:")
    for rule in (
        "At least 8 characters",
        "Not only numbers",
        "Not too similar to your name, username, or email",
        "Not a commonly used password",
    ):
        await user.should_see(rule)

    def passed_rules() -> int:
        with user:
            return sum(icon.name == "check_circle" for icon in user.find(kind=ui.icon).elements)

    assert passed_rules() == 0

    user.find("Password").type("12345678")
    assert passed_rules() == 1

    user.find("Password").clear().type("Sturdy-passphrase-42")
    assert passed_rules() == 2


async def test_login_with_wrong_password_shows_error(user: User, account) -> None:
    await open_login(user)
    user.find("Username").type(account["username"])
    user.find("Password").type("wrong-password")
    user.find("Sign in").click()

    await user.should_see("Invalid username or password.", retries=20)
    await user.should_not_see("Recent Items")


async def test_sign_out_returns_to_login_and_locks_pages(user: User, account) -> None:
    await sign_in(user, account)

    user.find("Sign out").click()
    await user.should_see("Sign in to your account", retries=20)

    await user.open("/reports")
    await user.should_see("Sign in to your account", retries=20)


# ------------------------------------------------------------
# NAVIGATION / REFRESH
# ------------------------------------------------------------

@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_protected_pages_redirect_to_login_when_signed_out(user: User, path: str) -> None:
    await user.open(path)

    await user.should_see("Sign in to your account", retries=20)


async def test_signed_in_user_can_open_every_page(user: User, account, api) -> None:
    api.create_category("Electronics")
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    pages = {
        "/dashboard": "Recent Items",
        "/inventory": "Inventory",
        "/categories": "Electronics",
        "/valuations": "Valuations",
        "/reports": "Reports",
        "/settings": "Settings",
        f"/add-item/{inventory_id}": "Add a new belonging to My Inventory",
    }
    for path, expected in pages.items():
        await user.open(path)
        await user.should_see(expected, retries=20)
        await user.should_not_see("Sign in to your account")


async def test_refreshing_pages_keeps_the_session(user: User, account, api) -> None:
    api.create_category("Electronics")
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    for _ in range(2):
        await user.open("/dashboard")
        await user.should_see("Recent Items", retries=20)
        await user.open(f"/add-item/{inventory_id}")
        await user.should_see("Add a new belonging to My Inventory", retries=20)
        await user.open("/categories")
        await user.should_see("Electronics", retries=20)


# ------------------------------------------------------------
# EMPTY INVENTORY / ADD ITEM / VIEW ITEM
# ------------------------------------------------------------

async def test_new_account_sees_empty_dashboard(user: User, account) -> None:
    await sign_in(user, account)

    with user:
        values = {label.text for label in user.find(kind=ui.label).elements}
    assert "0" in values
    assert "$0.00" in values
    await user.should_not_see(kind=ui.link)


async def test_add_valid_item_through_the_form(user: User, account, api) -> None:
    api.create_category("Electronics")
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    await user.open(f"/add-item/{inventory_id}")
    await user.should_see("Add a new belonging to My Inventory", retries=20)
    user.find("Item Name *").type("Laptop")
    user.find("Category *").click()
    user.find("Electronics").click()
    set_value(user, "Date Acquired *", "2026-01-15")
    set_value(user, "Purchase Price ($) *", 1200.50)
    user.find(kind=ui.button, content="Add Item").click()

    await user.should_see("Item added successfully.", retries=20)
    items = api.get("/api/items/").json()["items"]
    assert [(item["name"], item["category"], item["purchase_value"]) for item in items] == [
        ("Laptop", "Electronics", 1200.50)
    ]

    item_id = items[0]["public_id"]
    detail = api.item(item_id).json()["item"]
    assert detail["purchase_amount"] == "1200.50"
    assert detail["effective_value"] == "1200.50"
    # Wait for Add Item's actual redirect before checking the saved row.
    await user.should_see(marker=f"item-value-{item_id}", content="$1,200.50", retries=20)
    with user:
        assert next(iter(user.find(marker=f"item-value-{item_id}").elements)).text == "$1,200.50"


async def test_invalid_item_shows_errors_and_is_not_saved(user: User, account, api) -> None:
    api.create_category("Electronics")
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    await user.open(f"/add-item/{inventory_id}")
    await user.should_see("Add a new belonging to My Inventory", retries=20)
    set_value(user, "Date Acquired *", "")
    user.find(kind=ui.button, content="Add Item").click()

    await user.should_see("Couldn't add the item. Check the highlighted fields.", retries=20)
    await user.should_see("This field is required.")
    await user.should_not_see("Item added successfully.")
    assert api.get("/api/items/").json()["items"] == []


async def test_dashboard_lists_item_and_opens_it(user: User, account, api) -> None:
    category = api.create_category("Electronics")
    category_id = api.get(f"/api/inventory/{api.inventory_id()}/add-item/").json()["categories"][0]["id"]
    item_id = api.add_item(
        name="Laptop",
        category=category_id,
        purchase_date="2026-01-15",
        purchase_amount="1200.50",
        condition="used",
        quantity="1",
    )
    assert category["item_count"] == 0
    await sign_in(user, account)

    await user.should_see("$1,200.50")
    user.find(kind=ui.link, content="Laptop").click()

    await user.should_see("Item Information", retries=20)
    await user.should_see("Electronics")
    user.find(kind=ui.button, content="Edit Item").click()

    await user.should_see("Update the details for Laptop.", retries=20)
    with user:
        assert user.find("Item Name *").elements.pop().value == "Laptop"
        assert user.find("Category *").elements.pop().value == str(category_id)

    user.find("Item Name *").clear().type("Laptop Pro")
    user.find("Save Changes").click()
    await user.should_see("Item updated successfully.", retries=20)
    assert api.get(f"/api/item/{item_id}/").json()["item"]["name"] == "Laptop Pro"


async def test_missing_item_shows_not_found(user: User, account) -> None:
    await sign_in(user, account)

    await user.open(f"/edit-item/{uuid.uuid4()}")

    await user.should_see("Item not found", retries=20)


# ------------------------------------------------------------
# PERSISTENCE
# ------------------------------------------------------------

async def test_items_persist_for_a_new_browser_session(create_user, account, api) -> None:
    api.create_category("Electronics")
    category_id = api.get(f"/api/inventory/{api.inventory_id()}/add-item/").json()["categories"][0]["id"]
    api.add_item(
        name="Guitar",
        category=category_id,
        purchase_date="2025-05-01",
        purchase_amount="450.00",
        condition="used",
        quantity="1",
    )

    first_browser = create_user()
    await sign_in(first_browser, account)
    await first_browser.should_see("Guitar")
    first_browser.find("Sign out").click()
    await first_browser.should_see("Sign in to your account", retries=20)

    second_browser = create_user()
    await sign_in(second_browser, account)
    await second_browser.should_see("Guitar")
    await second_browser.should_see("$450.00")


# ------------------------------------------------------------
# BACKEND UNAVAILABLE / API ERRORS
# ------------------------------------------------------------

async def test_login_and_register_report_unreachable_backend(user: User, account, monkeypatch) -> None:
    make_backend_unreachable(monkeypatch)

    await open_login(user)
    user.find("Username").type(account["username"])
    user.find("Password").type(account["password"])
    user.find("Sign in").click()
    await user.should_see("Could not connect to the server. Try again.", retries=50)

    await user.open("/register")
    user.find("Password").type("Sturdy-passphrase-42")
    user.find("Confirm password").type("Sturdy-passphrase-42")
    user.find("Create account").click()
    await user.should_see("Could not connect to the server. Try again.", retries=50)


async def test_pages_still_render_when_backend_goes_down(user: User, account, api, monkeypatch) -> None:
    api.create_category("Electronics")
    inventory_id = api.inventory_id()
    await sign_in(user, account)

    make_backend_unreachable(monkeypatch)

    await user.open("/dashboard")
    await user.should_see("Recent Items", retries=50)

    await user.open(f"/edit-item/{uuid.uuid4()}")
    await user.should_see("Item not found", retries=50)

    await user.open(f"/item/{uuid.uuid4()}")
    await user.should_see("Item not found", retries=50)

    await user.open("/inventory")
    await user.should_see("Could not load your inventory.", retries=50)

    await user.open("/valuations")
    await user.should_see("Could not load inventory", retries=50)

    await user.open("/categories")
    await user.should_see("Categories", retries=50)

    await user.open("/reports")
    await user.should_see("Reports", retries=50)

    await user.open(f"/add-item/{inventory_id}")
    await user.should_see("Add Item", retries=50)
    await user.should_see("Could not load locations. Please try again.", retries=50)
    await user.should_see(marker="retry-locations")
    user.find("Item Name *").type("Laptop")
    user.find(kind=ui.button, content="Add Item").click()
    await user.should_see("Locations are unavailable. Retry loading locations before saving.", retries=50)
    assert api.get("/api/items/").json()["items"] == []


async def test_expired_backend_session_sends_user_back_to_login(user: User, account, api) -> None:
    await sign_in(user, account)

    # End the Django session behind the frontend's back (e.g. signed out elsewhere).
    stored = next(iter(app.storage._users.values()))  # pylint: disable=protected-access
    api.session.cookies.clear()
    api.session.cookies.set("sessionid", stored["auth_cookies"]["sessionid"])
    assert api.post("/api/auth/logout/").ok

    await user.open("/dashboard")
    await user.should_see("Your session expired. Please sign in again.", retries=20)
    await user.should_see("Sign in to your account")
