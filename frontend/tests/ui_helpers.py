"""Helpers shared by the NiceGUI simulated-user tests."""

import io
import inspect

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

UNREACHABLE_BACKEND = "http://127.0.0.1:9"


async def open_login(user: User) -> None:
    await user.open("/")
    await user.should_see("Sign in to your account", retries=20)


async def sign_in(user: User, account: dict) -> None:
    await open_login(user)
    user.find("Username").type(account["username"])
    user.find("Password").type(account["password"])
    click_button(user, "Sign in")
    await user.should_see("Recent Items", retries=20)


def set_value(user: User, label: str, value) -> None:
    with user:
        for element in user.find(label).elements:
            element.value = value


def click_button(user: User, text: str, index: int = 0, marker: str | None = None) -> None:
    with user:
        buttons = [
            button
            for button in user.find(kind=ui.button, content=text if marker is None else None, marker=marker).elements
            if button.text == text
        ]

    assert len(buttons) > index, (
        f"Expected button {text!r} at index {index}"
        f"{f' with marker {marker!r}' if marker else ''}, "
        f"but found {len(buttons)} matching buttons."
    )

    UserInteraction(user, {buttons[index]}, text).click()


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


async def upload_file(user: User, filename: str, content: bytes, content_type: str) -> None:
    """Use the real upload handler on both supported NiceGUI event formats."""
    with user:
        upload_element = user.find(kind=ui.upload).elements.pop()

        if hasattr(ui.upload, "SmallFileUpload"):
            upload = ui.upload.SmallFileUpload(filename, content_type, content)
        else:
            from starlette.datastructures import Headers, UploadFile

            upload = UploadFile(
                filename=filename,
                file=io.BytesIO(content),
                headers=Headers({"content-type": content_type}),
            )
        result = upload_element.handle_uploads([upload])
        if inspect.isawaitable(result):
            await result


def make_backend_unreachable(monkeypatch) -> None:
    from pages import (
        add_item, categories, dashboard, edit_item, inventory,
        item_detail, register, reports, valuations,
    )
    from utilities import inventory_switcher, location_management
    import backend_client

    for module in (
        backend_client, dashboard, register, add_item, edit_item, categories,
        reports, inventory, item_detail, valuations, inventory_switcher, location_management,
    ):
        monkeypatch.setattr(module, "BACKEND_URL", UNREACHABLE_BACKEND)
