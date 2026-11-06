"""Manage existing inventories from Settings using the current Django session."""

import requests
from nicegui import app, run, ui

from backend_client import BACKEND_URL, authenticated_session, csrf_headers
from utilities.inventory_switcher import InventoryApiError, _api_error


class InventorySessionExpired(InventoryApiError):
    """The Django login session no longer exists."""


def _inventory_request(
    cookies: dict,
    method: str,
    endpoint: str,
    payload: dict | None = None,
) -> tuple[dict, dict]:
    """Keep HTTP work off the UI loop and preserve Django session cookies."""
    with authenticated_session(cookies) as session:
        headers = csrf_headers(session) if method != "GET" else {}
        response = session.request(
            method,
            f"{BACKEND_URL}{endpoint}",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.status_code == 401:
            raise InventorySessionExpired("Your session expired. Please sign in again.")
        if not response.ok:
            raise InventoryApiError(_api_error(response))
        result = response.json()
        if not isinstance(result, dict):
            raise InventoryApiError("The server returned an unexpected response. Try again.")
        return result, session.cookies.get_dict()


def _sign_in_again() -> None:
    app.storage.user.pop("auth_cookies", None)
    app.storage.user.pop("username", None)
    ui.notify("Your session expired. Please sign in again.", type="warning")
    ui.navigate.to("/")


def show_inventory_management() -> None:
    """Render management controls without adding another create/switch flow."""
    state = {"busy": False, "editing": None, "archiving": None}

    with ui.card().classes("settings-card w-full p-6 gap-4").props("id=inventories"):
        ui.label("Manage inventories").classes("settings-section-title")
        ui.label(
            "Rename your inventories, update descriptions, or archive groups you no longer use."
        ).classes("text-sm muted")
        ui.label(
            "Keep at least one inventory. Use New in the inventory switcher to create "
            "a replacement before archiving your last inventory."
        ).classes("text-sm muted")
        with ui.column().classes("w-full gap-3") as inventory_list:
            ui.label("Loading inventories...").classes("text-sm muted")

    with ui.dialog().props("persistent").mark("edit-inventory-dialog") as edit_dialog:
        with ui.card().classes("w-[480px] max-w-full p-6 gap-4"):
            ui.label("Edit inventory").classes("text-xl font-bold")
            name_input = (
                ui.input("Inventory name")
                .props("outlined autofocus maxlength=255")
                .classes("w-full")
                .mark("edit-inventory-name")
            )
            description_input = (
                ui.textarea("Description (optional)")
                .props("outlined autogrow")
                .classes("w-full")
                .mark("edit-inventory-description")
            )
            edit_error = ui.label().classes("text-sm text-negative").props("role=alert")

            async def save_inventory() -> None:
                inventory = state["editing"]
                if state["busy"] or inventory is None:
                    return
                name = (name_input.value or "").strip()
                if not name:
                    edit_error.text = "Inventory name is required."
                    return
                if len(name) > 255:
                    edit_error.text = "Inventory name must be 255 characters or fewer."
                    return

                state["busy"] = True
                edit_error.text = ""
                for control in (save_button, edit_cancel, name_input, description_input):
                    control.disable()
                try:
                    _, cookies = await run.io_bound(
                        _inventory_request,
                        dict(app.storage.user.get("auth_cookies", {})),
                        "PATCH",
                        f'/api/inventories/{inventory["public_id"]}/',
                        {"name": name, "description": description_input.value or ""},
                    )
                except InventorySessionExpired:
                    edit_dialog.close()
                    _sign_in_again()
                except InventoryApiError as error:
                    edit_error.text = str(error)
                except (requests.RequestException, ValueError):
                    edit_error.text = "Could not save the inventory. Please try again."
                else:
                    app.storage.user["auth_cookies"] = cookies
                    edit_dialog.close()
                    ui.notify("Inventory updated.", type="positive")
                    # Rebuild both the settings list and the shared switcher.
                    ui.navigate.to("/settings")
                finally:
                    state["busy"] = False
                    for control in (save_button, edit_cancel, name_input, description_input):
                        control.enable()

            with ui.row().classes("w-full justify-end gap-2"):
                edit_cancel = ui.button("Cancel", on_click=edit_dialog.close).props(
                    "flat no-caps"
                ).mark("cancel-inventory-edit")
                save_button = ui.button("Save inventory", on_click=save_inventory).props(
                    "unelevated no-caps color=primary"
                )

    with ui.dialog().props("persistent").mark("archive-inventory-dialog") as archive_dialog:
        with ui.card().classes("w-[480px] max-w-full p-6 gap-4"):
            ui.label("Archive inventory?").classes("text-xl font-bold")
            archive_name = ui.label().classes("font-semibold break-words")
            ui.label(
                "Its items and attachments will be kept. This inventory will disappear "
                "from the inventory switcher."
            ).classes("text-sm muted")
            archive_note = ui.label().classes("text-sm muted")
            archive_error = ui.label().classes("text-sm text-negative").props("role=alert")

            async def archive_inventory() -> None:
                inventory = state["archiving"]
                if state["busy"] or inventory is None:
                    return
                state["busy"] = True
                archive_error.text = ""
                confirm_archive.disable()
                archive_cancel.disable()
                try:
                    _, cookies = await run.io_bound(
                        _inventory_request,
                        dict(app.storage.user.get("auth_cookies", {})),
                        "POST",
                        f'/api/inventories/{inventory["public_id"]}/archive/',
                        {},
                    )
                except InventorySessionExpired:
                    archive_dialog.close()
                    _sign_in_again()
                except InventoryApiError as error:
                    archive_error.text = str(error)
                except (requests.RequestException, ValueError):
                    archive_error.text = "Could not archive the inventory. Please try again."
                else:
                    app.storage.user["auth_cookies"] = cookies
                    archive_dialog.close()
                    ui.notify("Inventory archived.", type="positive")
                    # Django has selected a replacement if this was the current inventory.
                    ui.navigate.to("/settings")
                finally:
                    state["busy"] = False
                    confirm_archive.enable()
                    archive_cancel.enable()

            with ui.row().classes("w-full justify-end gap-2"):
                archive_cancel = ui.button("Cancel", on_click=archive_dialog.close).props(
                    "flat no-caps"
                ).mark("cancel-inventory-archive")
                confirm_archive = ui.button("Confirm archive", on_click=archive_inventory).props(
                    "unelevated no-caps color=negative"
                )

    def open_edit(inventory: dict) -> None:
        if state["busy"]:
            return
        state["editing"] = inventory
        name_input.value = inventory["name"]
        description_input.value = inventory.get("description", "")
        edit_error.text = ""
        edit_dialog.open()

    def open_archive(inventory: dict, active_id: str | None) -> None:
        if state["busy"]:
            return
        state["archiving"] = inventory
        archive_name.text = inventory["name"]
        archive_error.text = ""
        archive_note.text = (
            "This is your current inventory. Another available inventory will be selected automatically."
            if inventory["public_id"] == active_id
            else "Your current inventory will stay selected."
        )
        archive_dialog.open()

    async def load_inventories() -> None:
        try:
            result, cookies = await run.io_bound(
                _inventory_request,
                dict(app.storage.user.get("auth_cookies", {})),
                "GET",
                "/api/inventories/",
            )
        except InventorySessionExpired:
            _sign_in_again()
            return
        except (requests.RequestException, InventoryApiError, ValueError):
            inventory_list.clear()
            with inventory_list:
                ui.label("Could not load your inventories. Please try again.").classes(
                    "text-sm text-negative"
                ).props("role=alert")
                ui.button("Retry", on_click=load_inventories).props("outline no-caps")
            return

        app.storage.user["auth_cookies"] = cookies
        inventories = result.get("inventories", [])
        active_id = result.get("active_inventory_id")
        inventory_list.clear()
        with inventory_list:
            if not inventories:
                ui.label("No inventories available. Use New in the inventory switcher to create one.").classes(
                    "text-sm muted"
                )
            for inventory in inventories:
                inventory_id = inventory["public_id"]
                with ui.row().classes(
                    "w-full items-center justify-between gap-3 rounded-lg border border-slate-200 p-4"
                ).mark(f"inventory-{inventory_id}"):
                    with ui.column().classes("min-w-0 flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(inventory["name"]).classes("font-semibold break-words")
                            if inventory_id == active_id:
                                ui.badge("Current inventory", color="primary")
                        ui.label(inventory.get("description") or "No description").classes(
                            "text-sm muted whitespace-pre-wrap break-words"
                        )
                        count = inventory.get("item_count", 0)
                        ui.label(f'{count} {"item" if count == 1 else "items"}').classes("text-xs muted")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Edit", icon="edit", on_click=lambda inv=inventory: open_edit(inv)
                        ).props("outline no-caps color=primary").mark(f"edit-inventory-{inventory_id}")
                        archive_button = ui.button(
                            "Archive", icon="archive",
                            on_click=lambda inv=inventory: open_archive(inv, active_id),
                        ).props("flat no-caps color=negative").mark(f"archive-inventory-{inventory_id}")
                        if len(inventories) <= 1:
                            archive_button.disable()
                            archive_button.tooltip("Create another inventory before archiving this one.")

    ui.timer(0.1, load_inventories, once=True)
