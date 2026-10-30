"""Account and Security journeys through Settings."""

import uuid

import pytest
from nicegui import app
from nicegui.testing import User

from tests import app_under_test
from tests.conftest import PASSWORD
from tests.ui_helpers import click_button, sign_in

pytestmark = pytest.mark.module_under_test(app_under_test)

NEW_PASSWORD = "Fresh-passphrase-77"


async def open_settings(user: User, account: dict) -> None:
    await sign_in(user, account)
    await user.open("/settings")
    await user.should_see("Save Account", retries=20)


def field_value(user: User, marker: str) -> str:
    with user:
        return next(iter(user.find(marker=marker).elements)).value


def can_sign_in(api, username: str, password: str) -> bool:
    response = type(api)(api.url).post(
        "/api/auth/login/",
        json={"username": username, "password": password},
    )
    return response.status_code == 200


async def test_settings_loads_current_account_details(user: User, account) -> None:
    await open_settings(user, account)

    assert field_value(user, "account-first-name") == "Test"
    assert field_value(user, "account-last-name") == "User"
    assert field_value(user, "account-email") == f'{account["username"]}@example.com'
    await user.should_see(account["username"])


async def test_save_account_persists_changes(user: User, account, api) -> None:
    await open_settings(user, account)
    user.find(marker="account-first-name").clear().type("  Jamie ")
    user.find(marker="account-last-name").clear().type("Rivera")
    user.find(marker="account-email").clear().type("jamie.rivera@example.com")
    user.find("Save Account").click()

    await user.should_see("Account updated.", retries=20)
    assert field_value(user, "account-first-name") == "Jamie"
    assert api.get("/api/account/").json()["account"] == {
        "first_name": "Jamie",
        "last_name": "Rivera",
        "email": "jamie.rivera@example.com",
        "username": account["username"],
    }


async def test_duplicate_and_invalid_email_are_rejected(user: User, account, api) -> None:
    other = type(api)(api.url)
    other_username = f"other_{uuid.uuid4().hex[:8]}"
    other.register(other_username)

    await open_settings(user, account)
    user.find(marker="account-email").clear().type(f"{other_username}@example.com")
    user.find("Save Account").click()
    await user.should_see("An account with this email already exists.", retries=20)

    user.find(marker="account-email").clear().type("not-an-email")
    user.find("Save Account").click()
    await user.should_see("Enter a valid email address.", retries=20)

    assert api.get("/api/account/").json()["account"]["email"] == f'{account["username"]}@example.com'


async def test_change_password_keeps_user_signed_in(user: User, account, api) -> None:
    await open_settings(user, account)
    click_button(user, "Change Password")
    await user.should_see("Change password")
    user.find(marker="current-password").type(PASSWORD)
    user.find(marker="new-password").type(NEW_PASSWORD)
    user.find(marker="new-password-confirm").type(NEW_PASSWORD)
    user.find("Update password").click()

    await user.should_see("Password changed.", retries=20)
    assert can_sign_in(api, account["username"], NEW_PASSWORD)
    assert not can_sign_in(api, account["username"], PASSWORD)

    # The rotated Django session cookie was stored, so this browser stays signed in.
    await user.open("/dashboard")
    await user.should_see("Recent Items", retries=20)
    assert app.storage.user.get("auth_cookies")


async def test_change_password_validation_keeps_dialog_open(user: User, account, api) -> None:
    await open_settings(user, account)
    click_button(user, "Change Password")
    user.find(marker="current-password").type("wrong-password")
    user.find(marker="new-password").type(NEW_PASSWORD)
    user.find(marker="new-password-confirm").type(NEW_PASSWORD)
    user.find("Update password").click()
    await user.should_see("Your current password is incorrect.", retries=20)

    user.find(marker="current-password").clear().type(PASSWORD)
    user.find(marker="new-password").clear().type("12345678")
    user.find(marker="new-password-confirm").clear().type("12345678")
    user.find("Update password").click()
    await user.should_see("This password is entirely numeric.", retries=20)
    await user.should_see("Change password")

    assert can_sign_in(api, account["username"], PASSWORD)
