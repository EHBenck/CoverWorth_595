from datetime import datetime
from urllib.parse import quote

import requests
from nicegui import app, ui

from backend_client import (
    BACKEND_URL,
    authenticated_session,
    csrf_headers,
)
from utilities.constants import CATEGORY_VISUALS, DEFAULT_VISUAL
from utilities.nav_wrapper import build_app_shell


# CSS
ui.add_css(
    """
    body {
        background: #f3f8fb;
        color: #0f172a;
        font-family: Inter, Roboto, Arial, sans-serif;
    }

    .nicegui-content {
        padding: 0 !important;
        background-color: #f3f8fb !important;
    }

    .categories-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }

    .categories-panel {
        width: 100%;
        background: #ffffff;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .category-filter-control
    .q-field__control {
        min-height: 52px;
    }

    .category-grid {
        display: grid;
        grid-template-columns:
            repeat(3, minmax(0, 1fr));
        width: 100%;
        gap: 16px;
    }

    .category-card {
        background: #ffffff;
        border: 1px solid #dbe5ef;
        border-radius: 12px;
        box-shadow:
            0 1px 4px rgba(15, 23, 42, 0.03);
        transition:
            box-shadow 0.15s ease,
            transform 0.15s ease,
            border-color 0.15s ease;
    }

    .category-card:hover {
        border-color: #bfd5ee;
        box-shadow:
            0 6px 16px rgba(15, 23, 42, 0.07);
        transform: translateY(-1px);
    }

    .category-icon-box {
        width: 96px;
        height: 96px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .category-name {
        color: #0f172a;
        font-size: 20px;
        font-weight: 700;
    }

    .category-count {
        color: #526785;
        font-size: 15px;
    }

    .category-value {
        color: #0f172a;
        font-size: 28px;
        font-weight: 700;
        line-height: 1.1;
    }

    .category-updated {
        color: #64748b;
        font-size: 14px;
    }

    .about-categories {
        width: 100%;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
    }

    .about-icon {
        width: 38px;
        height: 38px;
        background: #0d6efd;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .category-empty {
        min-height: 280px;
    }

    .category-dialog-card {
        width: 520px;
        max-width: calc(100vw - 32px);
        border-radius: 12px;
    }

    @media (max-width: 1150px) {
        .category-grid {
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 750px) {
        .category-grid {
            grid-template-columns: 1fr;
        }

        .category-icon-box {
            width: 78px;
            height: 78px;
        }
    }
""",
    shared=True,
)


# HELPERS
def category_visual(name: str) -> dict:
    return CATEGORY_VISUALS.get(
        name.strip().lower(),
        DEFAULT_VISUAL,
    )


def updated_label(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        now = datetime.now(parsed.tzinfo)

        days = max(
            0,
            (now - parsed).days,
        )

        if days == 0:
            return "Updated today"

        if days == 1:
            return "Updated 1d ago"

        if days < 7:
            return f"Updated {days}d ago"

        weeks = days // 7

        if weeks == 1:
            return "Updated 1w ago"

        return f"Updated {weeks}w ago"

    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        return "Recently updated"


def updated_days(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        now = datetime.now(parsed.tzinfo)

        return max(
            0,
            (now - parsed).days,
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        return 0


def fetch_inventory_id() -> str | None:

    try:
        response = authenticated_session().get(
            f"{BACKEND_URL}/api/dashboard/",
            timeout=5,
        )

        if response.status_code == 401:
            return None

        response.raise_for_status()

        return response.json().get("inventory_id")

    except requests.RequestException:
        return None


def fetch_categories(
    inventory_id: str,
) -> list[dict]:

    try:
        response = authenticated_session().get(
            (f"{BACKEND_URL}/api/inventory/" f"{inventory_id}/categories/"),
            timeout=5,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("categories", [])

    except requests.RequestException as error:
        print("Error loading categories:", error)
        return []


# PAGE
@ui.page("/categories")
def categories_page():

    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title("Categories | CoverWorth")

    build_app_shell(
        "Categories",
        username=app.storage.user.get(
            "username",
            "User",
        ),
    )

    inventory_id = fetch_inventory_id()

    if not inventory_id:
        with ui.column().classes(
            "page-content-frame " "items-center " "justify-center " "gap-3 p-8"
        ):
            ui.icon("inventory_2").classes("text-5xl text-slate-300")

            ui.label("No inventory found").classes("text-xl font-bold")

            ui.label(
                ("CoverWorth could not find an active inventory for this account.")
            ).classes("muted")
        return

    state = {"categories": fetch_categories(inventory_id)}

    editing_category = {"value": None}

    # API REFRESH
    def reload_categories():

        state["categories"] = fetch_categories(inventory_id)

        category_grid.refresh()

    # CREATE / EDIT DIALOG
    with ui.dialog() as category_dialog:
        with ui.card().classes("category-dialog-card p-6 gap-5"):
            with ui.column().classes("gap-0"):
                dialog_title = ui.label("Create Category").classes("text-2xl font-bold")

                dialog_subtitle = ui.label(
                    ("Create a category to organize your inventory.")
                ).classes("text-sm muted")

            category_name = (
                ui.input(
                    label="Category Name",
                )
                .props("outlined")
                .classes("w-full")
            )

            category_description = (
                ui.textarea(
                    label="Description",
                )
                .props("outlined autogrow")
                .classes("w-full")
            )

            dialog_error = ui.label().classes("text-sm text-red-600")

            def close_dialog():
                category_dialog.close()

                category_name.value = ""
                category_description.value = ""

                editing_category["value"] = None

                dialog_error.text = ""

            def save_category():
                name = (category_name.value or "").strip()

                description = (category_description.value or "").strip()

                if not name:
                    dialog_error.text = "Category name is required."
                    return

                session = authenticated_session()

                headers = csrf_headers(session)

                payload = {
                    "name": name,
                    "description": description,
                }

                try:
                    current = editing_category["value"]

                    if current is None:
                        response = session.post(
                            (
                                f"{BACKEND_URL}"
                                f"/api/inventory/"
                                f"{inventory_id}"
                                "/categories/"
                            ),
                            json=payload,
                            headers=headers,
                            timeout=5,
                        )
                    else:
                        response = session.put(
                            (
                                f"{BACKEND_URL}"
                                f"/api/category/"
                                f'{current["public_id"]}/'
                            ),
                            json=payload,
                            headers=headers,
                            timeout=5,
                        )

                    data = response.json()

                    if not response.ok:
                        errors = data.get(
                            "errors",
                            {},
                        )

                        first_error = next(
                            iter(errors.values()),
                            data.get(
                                "error",
                                ("Unable to save " "category."),
                            ),
                        )

                        if isinstance(
                            first_error,
                            list,
                        ):
                            first_error = (
                                first_error[0] if first_error else "Unable to save."
                            )

                        dialog_error.text = str(first_error)

                        return

                    action = "created" if current is None else "updated"

                    ui.notify(
                        (f'Category "{name}" ' f"{action}."),
                        type="positive",
                    )

                    close_dialog()

                    reload_categories()

                except requests.RequestException:
                    dialog_error.text = "Could not connect to the backend."

            with ui.row().classes("w-full justify-end gap-3"):
                ui.button(
                    "Cancel",
                    on_click=close_dialog,
                ).props("flat " "color=grey-7 " "no-caps")

                ui.button(
                    "Save Category",
                    icon="check",
                    on_click=save_category,
                ).props(
                    "unelevated " "color=primary " "no-caps"
                ).classes("px-5")

    def open_create():

        editing_category["value"] = None

        dialog_title.text = "Create Category"

        dialog_subtitle.text = "Create a category to organize your inventory."

        category_name.value = ""

        category_description.value = ""

        dialog_error.text = ""

        category_dialog.open()

    def open_edit(category):

        editing_category["value"] = category

        dialog_title.text = "Edit Category"

        dialog_subtitle.text = "Update this category's name or description."

        category_name.value = category["name"]

        category_description.value = category.get(
            "description",
            "",
        )

        dialog_error.text = ""

        category_dialog.open()

    # DELETE
    def open_delete(category):
        with ui.dialog() as dialog:
            with ui.card().classes(
                "w-[460px] " "max-w-[calc(100vw-32px)] " "p-6 gap-5"
            ):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("warning_amber").classes("text-3xl text-red-600")

                    with ui.column().classes("gap-0"):

                        ui.label(("Delete " f'{category["name"]}?')).classes(
                            "text-xl font-bold"
                        )

                        ui.label(
                            (
                                f'{category["item_count"]} '
                                "items currently use "
                                "this category."
                            )
                        ).classes("text-sm muted")

                ui.label(
                    (
                        "Items using this category "
                        "will become Uncategorized. "
                        "The items themselves will "
                        "not be deleted."
                    )
                ).classes("text-sm text-slate-700")

                def confirm_delete():

                    session = authenticated_session()

                    try:
                        response = session.delete(
                            (
                                f"{BACKEND_URL}"
                                f"/api/category/"
                                f'{category["public_id"]}/'
                            ),
                            headers=csrf_headers(session),
                            timeout=5,
                        )

                        if not response.ok:

                            ui.notify(
                                ("Unable to delete " "category."),
                                type="negative",
                            )

                            return

                        dialog.close()

                        ui.notify(
                            (f'{category["name"]} ' "deleted."),
                            type="positive",
                        )

                        reload_categories()

                    except requests.RequestException:
                        ui.notify(
                            ("Could not connect " "to the backend."),
                            type="negative",
                        )

                with ui.row().classes("w-full justify-end gap-3"):
                    ui.button(
                        "Cancel",
                        on_click=dialog.close,
                    ).props("flat " "color=grey-7 " "no-caps")

                    ui.button(
                        "Delete Category",
                        icon="delete",
                        on_click=confirm_delete,
                    ).props("unelevated " "color=negative " "no-caps")

        dialog.open()

    # PAGE CONTENT
    with ui.column().classes("categories-container " "page-content-frame " "p-7 gap-5"):

        with ui.row().classes("w-full " "items-center " "justify-between"):
            with ui.column().classes("gap-0"):
                ui.label("Categories").classes(
                    "text-4xl " "font-bold " "tracking-tight"
                )

                ui.label(("Organize your inventory " "by category")).classes(
                    "text-base muted"
                )

            ui.button(
                "New Category",
                icon="add",
                on_click=open_create,
            ).props(
                "unelevated " "color=primary " "no-caps"
            ).classes("px-5 py-2 rounded-lg")

        with ui.card().classes("categories-panel " "w-full p-4 gap-5"):

            def refresh_grid():
                category_grid.refresh()

            with ui.row().classes("w-full " "items-center " "gap-4 flex-wrap"):
                search = (
                    ui.input(
                        placeholder=("Search categories..."),
                        on_change=lambda _: refresh_grid(),
                    )
                    .props("outlined " "prepend-icon=search " "clearable")
                    .classes("category-filter-control " "min-w-[300px] flex-1")
                )

                with ui.row().classes("items-center gap-2"):
                    ui.label("Sort by").classes("text-sm muted")

                    sort_by = (
                        ui.select(
                            [
                                "Value",
                                "Name",
                                "Item Count",
                                "Recently Updated",
                            ],
                            value="Value",
                            on_change=lambda _: refresh_grid(),
                        )
                        .props("outlined options-dense")
                        .classes("category-filter-control " "w-[210px]")
                    )

            @ui.refreshable
            def category_grid():
                query = (search.value or "").strip().lower()

                categories = [
                    category
                    for category in state["categories"]
                    if (
                        not query
                        or query in category["name"].lower()
                        or query
                        in category.get(
                            "description",
                            "",
                        ).lower()
                    )
                ]

                if sort_by.value == "Value":
                    categories.sort(
                        key=lambda item: item["total_value"],
                        reverse=True,
                    )
                elif sort_by.value == "Name":
                    categories.sort(key=lambda item: item["name"].lower())
                elif sort_by.value == "Item Count":
                    categories.sort(
                        key=lambda item: item["item_count"],
                        reverse=True,
                    )

                else:
                    categories.sort(key=lambda item: updated_days(item["updated_at"]))

                if not categories:
                    with ui.column().classes(
                        "category-empty " "w-full items-center " "justify-center gap-2"
                    ):
                        ui.icon("category").classes("text-6xl " "text-slate-300")

                        ui.label("No categories found").classes(
                            "text-lg " "font-semibold " "text-slate-600"
                        )

                        ui.label(
                            ("Create your first category or change your search.")
                        ).classes("text-sm muted")
                    return

                with ui.element("div").classes("category-grid"):
                    for category in categories:
                        visual = category_visual(category["name"])
                        with ui.card().classes("category-card " "w-full p-5 gap-4"):
                            with ui.row().classes(
                                "w-full " "items-start " "gap-4 flex-nowrap"
                            ):
                                with ui.element("div").classes(
                                    "category-icon-box"
                                ).style(("background: " f'{visual["background"]};')):
                                    ui.icon(visual["icon"]).classes("text-5xl").style(
                                        ("color: " f'{visual["color"]};')
                                    )

                                with ui.column().classes("gap-1 flex-1"):
                                    ui.label(category["name"]).classes("category-name")

                                    ui.label(
                                        (f'{category["item_count"]:,} ' "items")
                                    ).classes("category-count")

                                    ui.label(
                                        (f'${category["total_value"]:,.0f}')
                                    ).classes("category-value mt-1")

                                    with ui.row().classes("items-center " "gap-2 mt-1"):
                                        ui.icon("schedule").classes(
                                            "text-[18px] " "text-slate-500"
                                        )

                                        ui.label(
                                            updated_label(category["updated_at"])
                                        ).classes("category-updated")

                                with ui.button(icon="more_vert").props(
                                    "flat " "round " "dense " "color=grey-9"
                                ):
                                    with ui.menu():
                                        ui.menu_item(
                                            "Edit Category",
                                            on_click=(
                                                lambda category=category: open_edit(
                                                    category
                                                )
                                            ),
                                        )

                                        ui.menu_item(
                                            "View Items",
                                            on_click=(
                                                lambda category=category: ui.navigate.to(
                                                    (
                                                        "/inventory"
                                                        "?category="
                                                        f'{quote(category["name"])}'
                                                    )
                                                )
                                            ),
                                        )

                                        ui.separator()

                                        ui.menu_item(
                                            "Delete Category",
                                            on_click=(
                                                lambda category=category: open_delete(
                                                    category
                                                )
                                            ),
                                        )

                            ui.separator()

                            ui.button(  # CATEGORY NAME BUTTON NAVIGATION LOGIC
                                "View Items",
                                icon="arrow_forward",
                                on_click=(
                                    lambda category=category: ui.navigate.to(
                                        (
                                            "/inventory"
                                            "?category="
                                            f'{quote(category["name"])}'
                                        )
                                    )
                                ),
                            ).props(
                                "flat " "color=primary " "no-caps " "icon-right"
                            ).classes(
                                "self-start " "font-semibold"
                            )

            category_grid()

            with ui.row().classes(
                "about-categories " "items-center gap-4 " "p-4 flex-nowrap"
            ):
                with ui.element("div").classes("about-icon"):
                    ui.icon("info").classes("text-xl")

                with ui.column().classes("gap-0"):
                    ui.label("About Categories").classes(
                        "text-base " "font-semibold " "text-slate-900"
                    )

                    ui.label(
                        (
                            "Categories help you organize your inventory items. Categories created here are available when adding or editing items."
                        )
                    ).classes("text-sm text-slate-600")
