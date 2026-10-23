"""Helpers shared by the NiceGUI simulated-user tests."""

import io

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from starlette.datastructures import Headers, UploadFile

UNREACHABLE_BACKEND = "http://127.0.0.1:9"


async def open_login(user: User) -> None:
    await user.open("/")
    await user.should_see("Sign in to your account", retries=20)


async def sign_in(user: User, account: dict) -> None:
    await open_login(user)
    user.find("Username").type(account["username"])
    user.find("Password").type(account["password"])
    user.find("Sign in").click()
    await user.should_see("Recent Items", retries=20)


def set_value(user: User, label: str, value) -> None:
    with user:
        for element in user.find(label).elements:
            element.value = value


def click_button(user: User, text: str) -> None:
    """Click the button labelled exactly `text` ("Update", not "Update All")."""
    with user:
        buttons = {
            button for button in user.find(kind=ui.button, content=text).elements
            if button.text == text
        }
    assert buttons, f"no button labelled {text!r}"
    UserInteraction(user, buttons, text).click()


def click_icon_button(user: User, icon: str) -> None:
    with user:
        buttons = {
            button for button in user.find(kind=ui.button).elements
            if button.props.get("icon") == icon
        }
    assert buttons, f"no button with icon {icon!r}"
    UserInteraction(user, buttons, icon).click()


def click_menu_item(user: User, text: str) -> None:
    """ui.menu_item keeps its text in a child element, so find the item that contains it."""
    with user:
        items = {
            item for item in user.find(kind=ui.menu_item).elements
            if any(getattr(child, "text", None) == text for child in item.descendants())
        }
    assert items, f"no menu item labelled {text!r}"
    UserInteraction(user, items, text).click()


def upload_file(user: User, filename: str, content: bytes, content_type: str) -> None:
    """Simulate picking a file in the page's ui.upload."""
    upload = UploadFile(
        io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )
    with user:
        user.find(kind=ui.upload).elements.pop().handle_uploads([upload])


def make_backend_unreachable(monkeypatch) -> None:
    from pages import (
        add_item, categories, dashboard, edit_item, inventory,
        item_detail, register, reports, valuations,
    )
    from utilities import inventory_switcher
    import backend_client

    for module in (
        backend_client, dashboard, register, add_item, edit_item, categories,
        reports, inventory, item_detail, valuations, inventory_switcher,
    ):
        monkeypatch.setattr(module, "BACKEND_URL", UNREACHABLE_BACKEND)
