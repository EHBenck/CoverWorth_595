"""Physical-location controls shared by item forms and the inventory filter.

Locations remain scoped to the inventory in the URL. Dialog updates replace
only location options, so an unfinished item form is never discarded.
"""

import inspect
from collections.abc import Callable

import requests
from nicegui import app, run, ui

from backend_client import BACKEND_URL, authenticated_session, csrf_headers


class LocationApiError(Exception):
    """A location request was rejected by the backend."""


class LocationSessionExpired(LocationApiError):
    """The authenticated Django session is no longer valid."""


def _location_request(
    cookies: dict,
    method: str,
    endpoint: str,
    payload: dict | None = None,
) -> tuple[dict, dict]:
    """Run in an IO worker; UI storage is only read/written on the UI loop."""
    with authenticated_session(cookies) as session:
        response = session.request(
            method,
            f"{BACKEND_URL}{endpoint}",
            json=payload,
            headers=csrf_headers(session) if method != "GET" else {},
            timeout=10,
        )
        if response.status_code == 401:
            raise LocationSessionExpired("Your session expired. Please sign in again.")
        try:
            result = response.json()
        except ValueError as error:
            raise LocationApiError("The server returned an unexpected response. Please try again.") from error
        if not isinstance(result, dict):
            raise LocationApiError("The server returned an unexpected response. Please try again.")
        if not response.ok or result.get("success") is False:
            errors = result.get("errors", {})
            message = result.get("error")
            if not isinstance(message, str) and isinstance(errors, dict):
                for value in errors.values():
                    message = value[0] if isinstance(value, list) and value else value
                    if isinstance(message, str):
                        break
            raise LocationApiError(
                message if isinstance(message, str) else "Could not update the location. Please try again."
            )
        return result, session.cookies.get_dict()


def _sign_in_again() -> None:
    app.storage.user.pop("auth_cookies", None)
    app.storage.user.pop("username", None)
    ui.notify("Your session expired. Please sign in again.", type="warning")
    ui.navigate.to("/")


class LocationControls:
    """Render a searchable picker/filter and an in-place management dialog."""

    def __init__(
        self,
        inventory_id: str,
        *,
        locations: list[dict] | None = None,
        value: str | None = None,
        current_path: str = "",
        mode: str = "item",
        on_change: Callable | None = None,
        on_locations_changed: Callable | None = None,
        filter_location_ids: Callable[[], set[str]] | None = None,
    ) -> None:
        self.inventory_id = inventory_id
        self.mode = mode
        self.locations = list(locations or [])
        self.loaded = locations is not None
        self.loading = False
        self.busy = False
        self.editing = None
        self.archiving = None
        self.on_locations_changed = on_locations_changed
        self.filter_location_ids = filter_location_ids
        self._pending_selection = None
        self._changed = False

        options = self._options()
        selected = (value or "") if mode == "item" else (value or "all")
        if selected and selected not in options:
            # Preserve an existing assignment if the options request needs a retry.
            options[selected] = current_path or "Selected location"

        with ui.column().classes("w-full gap-2" if mode == "item" else "gap-1 min-w-[230px]"):
            with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                self.select = ui.select(
                    options,
                    value=selected,
                    label="Location (optional)" if mode == "item" else "Location",
                    with_input=True,
                    on_change=on_change,
                ).props("outlined clearable" if mode == "item" else "outlined dense").classes(
                    "form-control min-w-[220px] flex-1" if mode == "item" else "filter-control w-[230px]"
                ).mark("item-location" if mode == "item" else "inventory-location-filter")
                self.manage_button = ui.button(
                    "Manage Locations", icon="place", on_click=self.open_manager,
                ).props("outline no-caps color=primary").mark("manage-locations")
            if mode == "item":
                ui.label("Choose where this item is kept, or leave it unassigned.").classes("text-xs muted")
            self.error = ui.label().classes("text-sm text-negative").props("role=alert").mark("location-load-error")
            self.retry = ui.button("Retry locations", on_click=self.reload).props("flat no-caps").mark("retry-locations")
            self.retry.visible = False

        self._build_manager()
        self._update_enabled()
        if not self.loaded:
            ui.timer(0.1, self.reload, once=True)

    @property
    def ready(self) -> bool:
        return self.loaded and not self.loading and not self.busy

    @property
    def value(self) -> str:
        return self.select.value or ("" if self.mode == "item" else "all")

    def _options(self) -> dict[str, str]:
        options = {"": "Unassigned"} if self.mode == "item" else {"all": "All Locations", "unassigned": "Unassigned"}
        assigned = self.filter_location_ids() if self.mode == "filter" and self.filter_location_ids else None
        for location in sorted(self.locations, key=lambda row: row.get("path", row["name"]).casefold()):
            if assigned is not None and str(location["public_id"]) not in assigned:
                continue
            options[str(location["public_id"])] = location.get("path") or location["name"]
        return options

    def refresh_options(self) -> None:
        """Refresh assigned-location filters after item deletion or reassignment."""
        if not self.loaded:
            return
        options = self._options()
        selected = self.select.value
        if selected not in options:
            selected = "" if self.mode == "item" else "all"
        self.select.set_options(options, value=selected)

    def _parent_options(self) -> dict[str, str]:
        excluded = set()
        if self.editing:
            excluded.add(self.editing["public_id"])
            # A location cannot be moved below itself or one of its descendants.
            while True:
                descendants = {row["public_id"] for row in self.locations if row.get("parent_id") in excluded}
                previous = len(excluded)
                excluded.update(descendants)
                if len(excluded) == previous:
                    break
        return {"": "No parent (top level)", **{
            row["public_id"]: row.get("path") or row["name"]
            for row in sorted(self.locations, key=lambda row: row.get("path", row["name"]).casefold())
            if row["public_id"] not in excluded
        }}

    def _update_enabled(self) -> None:
        enabled = self.loaded and not self.loading and not self.busy
        for control in (self.select, self.name_input, self.description_input, self.parent_select, self.save_button):
            control.set_enabled(enabled)
        self.manage_button.set_enabled(not self.busy and not self.loading)
        self.cancel_edit.set_enabled(not self.busy)
        self.close_button.set_enabled(not self.busy)
        self.confirm_archive.set_enabled(not self.busy)
        self.archive_cancel.set_enabled(not self.busy)

    def _build_manager(self) -> None:
        with ui.dialog().props("persistent").mark("location-management-dialog") as self.dialog:
            with ui.card().classes("w-[720px] max-w-full p-6 gap-4"):
                ui.label("Manage Locations").classes("text-xl font-bold")
                ui.label(
                    "Organize places within this inventory. Add a parent to create paths such as Home → Basement."
                ).classes("text-sm muted")
                self.manager_error = ui.label().classes("text-sm text-negative").props("role=alert")
                self.manager_retry = ui.button("Retry", on_click=self.reload).props("outline no-caps").mark("retry-location-management")
                self.manager_retry.visible = False
                self.location_list = ui.column().classes("w-full gap-2 max-h-[260px] overflow-y-auto")
                ui.separator()
                self.editor_title = ui.label("Create location").classes("text-lg font-semibold")
                self.name_input = ui.input("Location name").props("outlined maxlength=255").classes("w-full").mark("location-name")
                self.parent_select = ui.select(
                    self._parent_options(), value="", label="Parent location (optional)", with_input=True,
                ).props("outlined clearable").classes("w-full").mark("location-parent")
                self.description_input = ui.textarea("Description (optional)").props("outlined autogrow").classes("w-full").mark("location-description")
                self.edit_error = ui.label().classes("text-sm text-negative").props("role=alert").mark("location-edit-error")
                with ui.row().classes("w-full justify-end gap-2"):
                    self.cancel_edit = ui.button("Cancel edit", on_click=self.reset_editor).props("flat no-caps").mark("cancel-location-edit")
                    self.cancel_edit.visible = False
                    self.save_button = ui.button("Create location", icon="add", on_click=self.save).props("unelevated color=primary no-caps").mark("save-location")
                with ui.row().classes("w-full justify-end"):
                    self.close_button = ui.button("Done", on_click=self.dialog.close).props("flat no-caps").mark("close-location-management")

        with ui.dialog().props("persistent").mark("archive-location-dialog") as self.archive_dialog:
            with ui.card().classes("w-[460px] max-w-full p-6 gap-4"):
                ui.label("Archive location?").classes("text-xl font-bold")
                self.archive_name = ui.label().classes("font-semibold break-words")
                ui.label(
                    "The location will disappear from available choices. Move its assigned items and archive child locations first."
                ).classes("text-sm muted")
                self.archive_error = ui.label().classes("text-sm text-negative").props("role=alert").mark("location-archive-error")
                with ui.row().classes("w-full justify-end gap-2"):
                    self.archive_cancel = ui.button("Cancel", on_click=self.archive_dialog.close).props("flat no-caps").mark("cancel-location-archive")
                    self.confirm_archive = ui.button("Confirm archive", on_click=self.archive).props("unelevated color=negative no-caps").mark("confirm-location-archive")
        self._render_list()

    def _render_list(self) -> None:
        self.location_list.clear()
        with self.location_list:
            if not self.locations:
                ui.label("No locations yet. Create one below.").classes("text-sm muted")
            for location in sorted(self.locations, key=lambda row: row.get("path", row["name"]).casefold()):
                location_id = location["public_id"]
                with ui.row().classes("w-full items-center justify-between gap-3 border rounded-lg p-3").mark(f"location-{location_id}"):
                    with ui.column().classes("flex-1 min-w-0 gap-1"):
                        ui.label(location.get("path") or location["name"]).classes("font-semibold break-words")
                        if location.get("description"):
                            ui.label(location["description"]).classes("text-sm muted break-words whitespace-pre-wrap")
                    with ui.row().classes("gap-1"):
                        ui.button("Edit", icon="edit", on_click=lambda row=location: self.open_edit(row)).props("flat no-caps").mark(f"edit-location-{location_id}")
                        ui.button("Archive", icon="archive", on_click=lambda row=location: self.open_archive(row)).props("flat no-caps color=negative").mark(f"archive-location-{location_id}")

    async def _request(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        result, cookies = await run.io_bound(
            _location_request, dict(app.storage.user.get("auth_cookies", {})), method, endpoint, payload,
        )
        app.storage.user["auth_cookies"] = cookies
        return result

    async def reload(self) -> bool:
        if self.loading:
            return False
        self.loading = True
        self._update_enabled()
        try:
            result = await self._request("GET", f"/api/inventory/{self.inventory_id}/locations/")
            locations = result.get("locations")
            if not isinstance(locations, list):
                raise LocationApiError("The server returned an unexpected response. Please try again.")
            self.locations = locations
            self.loaded = True
            self.error.text = ""
            self.manager_error.text = ""
            self.retry.visible = False
            self.manager_retry.visible = False
            options = self._options()
            selected = self._pending_selection if self._pending_selection is not None else self.select.value
            if selected not in options:
                if selected and selected not in ("all", "unassigned"):
                    ui.notify("The selected location is no longer available. Please choose another location if needed.", type="warning")
                selected = "" if self.mode == "item" else "all"
            self.select.set_options(options, value=selected)
            self._pending_selection = None
            parent_options = self._parent_options()
            self.parent_select.set_options(parent_options, value=self.parent_select.value if self.parent_select.value in parent_options else "")
            self._render_list()
            if self._changed and self.on_locations_changed:
                outcome = self.on_locations_changed()
                if inspect.isawaitable(outcome):
                    await outcome
            self._changed = False
            return True
        except LocationSessionExpired:
            self.dialog.close()
            self.archive_dialog.close()
            _sign_in_again()
        except (requests.RequestException, LocationApiError, ValueError, KeyError, TypeError):
            self.loaded = False
            self.error.text = "Could not load locations. Please try again."
            self.manager_error.text = "Could not load locations. Please try again."
            self.retry.visible = True
            self.manager_retry.visible = True
        finally:
            self.loading = False
            self._update_enabled()
        return False

    async def open_manager(self) -> None:
        if self.busy or self.loading:
            return
        self.reset_editor()
        self.dialog.open()
        await self.reload()

    def reset_editor(self) -> None:
        if self.busy:
            return
        self.editing = None
        self.editor_title.text = "Create location"
        self.name_input.value = ""
        self.description_input.value = ""
        self.parent_select.set_options(self._parent_options(), value="")
        self.edit_error.text = ""
        self.save_button.text = "Create location"
        self.save_button.props("icon=add")
        self.cancel_edit.visible = False

    def open_edit(self, location: dict) -> None:
        if self.busy or self.loading or not self.loaded:
            return
        self.editing = location
        self.editor_title.text = "Edit location"
        self.name_input.value = location["name"]
        self.description_input.value = location.get("description") or ""
        self.parent_select.set_options(self._parent_options(), value=location.get("parent_id") or "")
        self.edit_error.text = ""
        self.save_button.text = "Save location"
        self.save_button.props("icon=save")
        self.cancel_edit.visible = True

    async def save(self) -> None:
        if not self.ready:
            return
        name = (self.name_input.value or "").strip()
        if not name:
            self.edit_error.text = "Location name is required."
            return
        if len(name) > 255:
            self.edit_error.text = "Location name must be 255 characters or fewer."
            return
        editing = self.editing
        self.busy = True
        self.edit_error.text = ""
        self._update_enabled()
        try:
            result = await self._request(
                "PATCH" if editing else "POST",
                f'/api/location/{editing["public_id"]}/' if editing else f"/api/inventory/{self.inventory_id}/locations/",
                {"name": name, "description": self.description_input.value or "", "parent_id": self.parent_select.value or None},
            )
            if not editing and self.mode == "item":
                self._pending_selection = result.get("location", {}).get("public_id")
            self._changed = True
            # A completed write is not retried if the following refresh fails.
            self.busy = False
            self.reset_editor()
            await self.reload()
            ui.notify("Location updated." if editing else "Location created.", type="positive")
        except LocationSessionExpired:
            self.dialog.close()
            _sign_in_again()
        except LocationApiError as error:
            self.edit_error.text = str(error)
        except (requests.RequestException, ValueError):
            self.edit_error.text = "Could not save the location. Please try again."
        finally:
            self.busy = False
            self._update_enabled()

    def open_archive(self, location: dict) -> None:
        if self.busy or self.loading or not self.loaded:
            return
        self.archiving = location
        self.archive_name.text = location.get("path") or location["name"]
        self.archive_error.text = ""
        self.archive_dialog.open()

    async def archive(self) -> None:
        if self.busy or not self.archiving:
            return
        location = self.archiving
        self.busy = True
        self.archive_error.text = ""
        self._update_enabled()
        try:
            await self._request("DELETE", f'/api/location/{location["public_id"]}/')
            if self.select.value == location["public_id"]:
                self._pending_selection = "" if self.mode == "item" else "all"
            self._changed = True
            self.archive_dialog.close()
            self.busy = False
            if self.editing and self.editing["public_id"] == location["public_id"]:
                self.reset_editor()
            await self.reload()
            ui.notify("Location archived.", type="positive")
        except LocationSessionExpired:
            self.archive_dialog.close()
            self.dialog.close()
            _sign_in_again()
        except LocationApiError as error:
            self.archive_error.text = str(error)
        except (requests.RequestException, ValueError):
            self.archive_error.text = "Could not archive the location. Please try again."
        finally:
            self.busy = False
            self._update_enabled()
