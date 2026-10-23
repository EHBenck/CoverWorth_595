"""Inventory selector for the signed-in CoverWorth navigation bar.

The Django session is the source of truth for the active inventory. No UUID
is stored independently in NiceGUI; switching the inventory refreshes the
current page so the other screens request data for the newly active one.
"""

import asyncio

import requests
from nicegui import app, run, ui
from nicegui.element import Element

from backend_client import BACKEND_URL, authenticated_session, csrf_headers


class InventoryApiError(Exception):
    """An inventory request failed or the API rejected it."""


def _api_error(response: requests.Response) -> str:
    """Extract a useful API validation message without exposing a traceback."""
    try:
        data = response.json()
    except ValueError:
        return f"Inventory request failed (HTTP {response.status_code})."

    if isinstance(data, dict):
        if isinstance(data.get("error"), str):
            return data["error"]
        errors = data.get("errors")
        if isinstance(errors, dict):
            for messages in errors.values():
                if isinstance(messages, list) and messages:
                    return str(messages[0])
                if isinstance(messages, str):
                    return messages

    return f"Inventory request failed (HTTP {response.status_code})."


def _post_inventory(cookies: dict, endpoint: str, payload: dict) -> tuple[dict, dict]:
    """Use the existing authenticated Django session and CSRF protection."""
    session = authenticated_session(cookies)
    headers = csrf_headers(session)
    response = session.post(
        f"{BACKEND_URL}{endpoint}",
        json=payload,
        headers=headers,
        timeout=10,
    )
    if not response.ok:
        raise InventoryApiError(_api_error(response))
    return response.json(), session.cookies.get_dict()


def _fetch_inventories(cookies: dict) -> tuple[dict[str, str], str | None]:
    response = authenticated_session(cookies).get(
        f"{BACKEND_URL}/api/inventories/", timeout=5,
    )
    response.raise_for_status()
    result = response.json()
    options = {
        inventory["public_id"]: inventory["name"]
        for inventory in result.get("inventories", [])
    }
    active_id = result.get("active_inventory_id")
    return options, active_id


def show_inventory_switcher(active_page: str) -> None:
    """Render the inventory selector without blocking the shared page shell."""
    cookies = dict(app.storage.user.get("auth_cookies", {}))
    if not cookies:
        return

    with ui.row().classes("items-center") as switcher_container:
        loading_label = ui.label("Loading inventories...").classes(
            "text-sm text-grey-7"
        )

    async def load_switcher() -> None:
        try:
            options, active_id = await run.io_bound(_fetch_inventories, cookies)
        except (requests.RequestException, ValueError) as error:
            loading_label.text = "Inventories unavailable"
            loading_label.classes("text-negative")
            loading_label.tooltip(str(error))
            return

        loading_label.delete()
        _render_inventory_switcher(
            active_page,
            cookies,
            options,
            active_id,
            switcher_container,
        )

    ui.timer(0.1, load_switcher, once=True)


def _render_inventory_switcher(
    active_page: str,
    cookies: dict,
    options: dict[str, str],
    active_id: str | None,
    container: Element,
) -> None:
    state = {"active_id": active_id, "busy": False}

    def refresh_after_switch() -> None:
        # Add/Edit Item URLs refer to a particular inventory or item. Return
        # to the inventory page instead of keeping a stale editing context.
        request = ui.context.client.request
        current_path = request.url.path if request else ""
        if current_path.startswith(("/add-item/", "/edit-item/")):
            ui.navigate.to("/inventory")
        else:
            ui.navigate.reload()

    async def select_inventory(event) -> None:
        new_id = event.value
        if state["busy"] or not new_id or new_id == state["active_id"]:
            return

        state["busy"] = True
        dropdown.disable()
        try:
            _, new_cookies = await asyncio.to_thread(
                _post_inventory,
                dict(app.storage.user.get("auth_cookies", {})),
                "/api/inventories/select/",
                {"inventory_id": new_id},
            )
        except (requests.RequestException, InventoryApiError, ValueError) as error:
            ui.notify(f"Could not switch inventory: {error}", type="negative")
            # Restore the visible selection; don't issue a second API call.
            dropdown.value = state["active_id"]
        else:
            app.storage.user["auth_cookies"] = new_cookies
            state["active_id"] = new_id
            ui.notify(f"Switched to {options[new_id]}", type="positive")
            refresh_after_switch()
        finally:
            dropdown.enable()
            state["busy"] = False

    with ui.dialog() as create_dialog:
        with ui.card().classes("w-96 max-w-full p-5 gap-4"):
            ui.label("Create Inventory").classes("text-xl font-bold")
            name_input = ui.input("Inventory name").props("outlined autofocus").classes("w-full")
            description_input = ui.textarea("Description (optional)").props("outlined").classes("w-full")

            async def create_inventory() -> None:
                name = (name_input.value or "").strip()
                if not name:
                    ui.notify("Please enter an inventory name.", type="warning")
                    return
                if state["busy"]:
                    return

                state["busy"] = True
                create_button.disable()
                try:
                    _, new_cookies = await asyncio.to_thread(
                        _post_inventory,
                        dict(app.storage.user.get("auth_cookies", {})),
                        "/api/inventories/",
                        {"name": name, "description": description_input.value or ""},
                    )
                except (requests.RequestException, InventoryApiError, ValueError) as error:
                    ui.notify(f"Could not create inventory: {error}", type="negative")
                else:
                    app.storage.user["auth_cookies"] = new_cookies
                    create_dialog.close()
                    ui.notify(f"Created inventory: {name}", type="positive")
                    # Django automatically selects the inventory it creates.
                    ui.navigate.to("/inventory")
                finally:
                    create_button.enable()
                    state["busy"] = False

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=create_dialog.close).props("flat no-caps")
                create_button = ui.button("Create", on_click=create_inventory).props(
                    "unelevated color=primary no-caps"
                )

    with container:
        with ui.row().classes("items-center gap-1"):
            dropdown = ui.select(
                options=options,
                value=active_id,
                label="Inventory",
                on_change=select_inventory,
            ).props("outlined dense options-dense").classes("w-44 max-w-[28vw]")
            ui.button("New", icon="add", on_click=create_dialog.open).props(
                "flat dense no-caps color=primary"
            ).tooltip("Create inventory")
