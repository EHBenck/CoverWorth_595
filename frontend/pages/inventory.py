import asyncio

from nicegui import app, run, ui
import requests
from utilities.nav_wrapper import build_app_shell
from utilities.inventory_table import add_view_mode_toggle, render_data_table
from backend_client import (
    BACKEND_URL,
    authenticated_session,
)



# COVERWORTH - INVENTORY PAGE
# ------------------------------------------------------------
# Mock data is used for now.
# TODO replace with live backend data.



# STYLING
ui.add_css("""
    body {
        background: #f4f7fb;
        color: #0f172a;
        font-family: Inter, Roboto, Arial, sans-serif;
    }

    .nicegui-content {
        padding: 0 !important;
    }


    /* ========================================================
       INVENTORY PAGE
       ======================================================== */

    .inventory-card {
        background: white;

        border: 1px solid #e1e7ef;
        border-radius: 12px;

        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .muted {
        color: #64748b;
    }


    /* ========================================================
       FILTER CONTROLS
       ======================================================== */

    .filter-control .q-field__control {
        min-height: 44px;
    }


    .inventory-table.grid-view {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 16px;
        min-width: 0;
    }

    .inventory-table.grid-view .table-header {
        display: none !important;
    }

    .inventory-table.grid-view .inventory-row {
        display: grid;
        grid-template-columns: 32px 1fr auto !important;
        grid-template-areas:
            "check image actions"
            "name name name"
            "category category category"
            "value status status";
        gap: 12px;
        align-items: center;
        min-height: 190px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: white;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(1) {
        grid-area: check;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(2) {
        grid-area: image;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(3) {
        grid-area: name;
        font-size: 16px;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(4) {
        grid-area: category;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(5) {
        grid-area: value;
        font-size: 18px;
        font-weight: 700;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(6) {
        grid-area: status;
        justify-self: end;
    }

    .inventory-table.grid-view .inventory-row > :nth-child(7) {
        grid-area: actions;
    }

    @media (max-width: 600px) {
        .inventory-table.grid-view {
            grid-template-columns: 1fr;
        }
    }


    /* ========================================================
       ITEM IMAGE PLACEHOLDER
       ======================================================== */

    .item-icon {
        width: 48px;
        height: 48px;

        background: #f1f5f9;

        border-radius: 8px;

        display: flex;
        align-items: center;
        justify-content: center;
    }


    /* ========================================================
       STATUS BADGES
       ======================================================== */

    .status-current {
        display: inline-block;

        width: fit-content;

        padding: 5px 12px;

        border-radius: 999px;

        background: #dcfce7;
        color: #166534;

        font-size: 12px;
        font-weight: 600;
    }

    .status-review {
        display: inline-block;

        width: fit-content;

        padding: 5px 12px;

        border-radius: 999px;

        background: #fef3c7;
        color: #92400e;

        font-size: 12px;
        font-weight: 600;
    }


    /* ========================================================
       TABLE FOOTER
       ======================================================== */

    .table-footer {
        width: 100%;

        padding: 14px 12px 4px 12px;
    }
""", shared=True)


def fetch_inventory_id(cookies: dict | None = None) -> str | None:
    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/dashboard/",
            timeout=5,
        )

        if response.status_code == 401:
            return None

        response.raise_for_status()

        return response.json().get("inventory_id")

    except requests.RequestException as error:
        print("Error fetching inventory ID:", error)
        return None



def fetch_inventory_items(
    inventory_id: str,
    cookies: dict | None = None,
) -> list[dict]:
    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL.rstrip('/')}/api/inventory/{inventory_id}/",
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])

        normalized_items = []

        for item in items:
            estimated_value = item.get("current_estimated_amount")

            if estimated_value is None:
                estimated_value = item.get("manual_value")

            if estimated_value is None:
                estimated_value = item.get("estimated_value")

            normalized_items.append({
                **item,
                "name": item.get("name") or "Unnamed Item",
                "category": item.get("category") or "Uncategorized",
                "location": item.get("location") or "",
                "estimated_value": (
                    float(estimated_value)
                    if estimated_value is not None
                    else 0.0
                ),
                "status": (
                    "Current"
                    if estimated_value is not None
                    else "Review"
                ),
                "icon": item.get("icon") or "inventory_2",
            })

        return normalized_items

    except (requests.RequestException, ValueError, TypeError) as error:
        print(f"[INVENTORY] Failed to fetch items: {error}")
        return []



def fetch_inventory_categories(
    inventory_id: str,
    cookies: dict | None = None,
) -> list[dict]:
    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/inventory/{inventory_id}/categories/",
            timeout=5,
        )

        response.raise_for_status()

        return response.json().get("categories", [])

    except requests.RequestException as error:
        print("Error fetching categories:", error)
        return []

# INVENTORY PAGE
@ui.page("/inventory")
async def inventory_page():
    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title(
        "Inventory | CoverWorth"
    )

    build_app_shell("Inventory")

    with ui.column().classes(
        "inventory-container page-content-frame "
        "items-center justify-center gap-3 p-8"
    ) as loading:
        ui.spinner(size="lg")
        ui.label("Loading inventory...").classes("muted")

    await ui.context.client.connected()
    cookies = dict(app.storage.user.get("auth_cookies", {}))
    inventory_id = await run.io_bound(fetch_inventory_id, cookies)

    if not inventory_id:
        loading.delete()
        ui.label(
            "Could not load your inventory. "
            "Please sign in or check your backend connection."
        ).classes("text-red-600 p-6")
        return

    items, categories = await asyncio.gather(
        run.io_bound(fetch_inventory_items, inventory_id, cookies),
        run.io_bound(fetch_inventory_categories, inventory_id, cookies),
    )
    loading.delete()

    state = {
        "items": items,
        "categories": categories,
    }

    def reload_inventory():
        state["items"] = fetch_inventory_items(inventory_id)
        state["categories"] = fetch_inventory_categories(inventory_id)
        inventory_rows.refresh()


    # MAIN PAGE CONTENT
    with ui.column().classes(
        "inventory-container page-content-frame p-7 gap-5"
    ):

        # PAGE TITLE
        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            with ui.column().classes(
                "gap-0"
            ):

                ui.label(
                    "Inventory"
                ).classes(
                    "text-4xl "
                    "font-bold "
                    "tracking-tight"
                )

                ui.label(
                    "View and manage all of your items"
                ).classes(
                    "text-base muted"
                )


            ui.button(
                "Add Item",
                icon="add",
                on_click=lambda: ui.navigate.to(
                    f"/add-item/{inventory_id}?return_to=%2Finventory"
                )
            ).props(
                "unelevated "
                "color=primary "
                "no-caps"
            ).classes(
                "px-5 py-2 rounded-lg"
            )

        # INVENTORY CARD
        with ui.card().classes(
            "inventory-card w-full p-4 gap-4"
        ):
            
            # FILTER CONTROLS
            with ui.row().classes(
                "w-full "
                "items-center "
                "gap-3 "
                "flex-wrap"
            ):


                def refresh_inventory():
                    inventory_rows.refresh()


                # SEARCH
                search_input = ui.input(
                    placeholder="Search your inventory...",
                    on_change=lambda _:
                    refresh_inventory(),
                ).props(
                    "outlined dense "
                    "prepend-icon=search "
                    "clearable"
                ).classes(
                    "filter-control "
                    "min-w-[260px] "
                    "flex-1"
                )

                # CATEGORY FILTER
                category_options = { 
                    "All Categories": "All Categories",
                    **{
                        category["name"]: category["name"]
                        for category in state["categories"]
                    },
                }

                category_filter = ui.select(
                    category_options,
                    value="All Categories",
                    on_change=lambda _: refresh_inventory(),
                ).props(
                    "outlined dense"
                ).classes(
                    "filter-control w-[190px]"
                )

                # LOCATION/STATUS FILTER
                locations = sorted({
                    item["location"]
                    for item in state["items"]
                    if item.get("location")
                })

                statuses = sorted({
                    item["status"]
                    for item in state["items"]
                    if item.get("status")
                })

                location_filter = ui.select(
                    ["All Locations", *locations],
                    value="All Locations",
                    on_change=lambda _: refresh_inventory(),
                ).props("outlined dense").classes(
                    "filter-control w-[190px]"
                )

                status_filter = ui.select(
                    ["All Statuses", *statuses],
                    value="All Statuses",
                    on_change=lambda _: refresh_inventory(),
                ).props("outlined dense").classes(
                    "filter-control w-[170px]"
                )

            view_mode = add_view_mode_toggle(
                lambda: inventory_rows.refresh()
            )
            
            # INVENTORY TABLE
            @ui.refreshable
            def inventory_rows():

                # CURRENT FILTER VALUES
                search_text = (
                    search_input.value or ""
                ).strip().lower()

                category = (
                    category_filter.value
                )

                location = (
                    location_filter.value
                )

                status = (
                    status_filter.value
                )

                # FILTER ITEMS
                filtered_items = []

                for item in state["items"]:

                    # SEARCH
                    if search_text:

                        searchable_text = (
                            f'{item["name"]} '
                            f'{item["category"]} '
                            f'{item["location"]}'
                        ).lower()

                        if (
                            search_text
                            not in searchable_text
                        ):
                            continue


                    # CATEGORY
                    if (
                        category != "All Categories"
                        and
                        item["category"] != category
                    ):
                        continue


                    # LOCATION
                    if (
                        location != "All Locations"
                        and
                        item["location"] != location
                    ):
                        continue


                    # STATUS
                    if (
                        status != "All Statuses"
                        and
                        item["status"] != status
                    ):
                        continue


                    filtered_items.append(
                        item
                    )


                def render_inventory_header():
                    ui.label("Image")
                    with ui.row().classes("items-center gap-1"):
                        ui.label("Item Name")
                        ui.icon("arrow_upward").classes("text-sm text-blue-600")
                    ui.label("Category")
                    with ui.row().classes("items-center gap-1"):
                        ui.label("Estimated Value")
                        ui.icon("unfold_more").classes("text-sm")
                    ui.label("Status")
                    ui.label("Actions")

                def render_inventory_row(item):
                    with ui.element("div").classes("item-icon"):
                        ui.icon(item["icon"]).classes("text-2xl text-slate-600")

                    ui.label(item["name"]).classes("text-sm font-semibold")
                    ui.label(item["category"]).classes("text-sm text-slate-700")
                    ui.label(f'${item["estimated_value"]:,.0f}').classes(
                        "text-sm font-medium"
                    )

                    if item["status"] == "Current":
                        ui.label("Current").classes("status-current")
                    else:
                        ui.label("Review").classes("status-review")

                    with ui.button(icon="more_vert").props(
                        "flat round dense color=grey-8"
                    ):
                        with ui.menu():
                            ui.menu_item(
                                "View Item",
                                on_click=lambda item=item: ui.notify(
                                    f'View {item["name"]}'
                                ),
                            )
                            ui.menu_item(
                                "Edit",
                                on_click=lambda item=item: ui.notify(
                                    f'Edit {item["name"]}'
                                ),
                            )
                            ui.separator()
                            ui.menu_item(
                                "Delete",
                                on_click=lambda item=item: ui.notify(
                                    f'Delete {item["name"]}'
                                ),
                            )

                def render_inventory_footer():
                    with ui.row().classes(
                        "table-footer items-center justify-between"
                    ):
                        ui.label(
                            f"Showing {len(filtered_items)} "
                            f"of {len(state['items'])} items"
                        ).classes("text-sm muted")

                        with ui.row().classes("items-center gap-4"):
                            ui.label("Rows per page:").classes("text-sm muted")
                            ui.select([8, 16, 24], value=8).props(
                                "dense borderless"
                            ).classes("w-16")

                            if filtered_items:
                                ui.label(
                                    f"1–{len(filtered_items)} "
                                    f"of {len(filtered_items)}"
                                ).classes("text-sm")
                            else:
                                ui.label("0 of 0").classes("text-sm")

                            ui.button(icon="chevron_left").props(
                                "flat round disable color=grey-6"
                            )
                            ui.button(
                                icon="chevron_right",
                                on_click=lambda: ui.notify(
                                    "Pagination will become active when more data is loaded."
                                ),
                            ).props("flat round color=primary")

                render_data_table(
                    filtered_items,
                    view_mode=view_mode,
                    grid_columns=(
                        "50px 75px minmax(200px, 1.8fr) "
                        "minmax(140px, 1fr) minmax(150px, 1fr) "
                        "minmax(120px, 0.8fr) 70px"
                    ),
                    wrapper_class="inventory-table-wrapper",
                    table_class="inventory-table",
                    header_class="inventory-grid table-header",
                    row_class="inventory-grid inventory-row",
                    render_header=render_inventory_header,
                    render_row=render_inventory_row,
                    empty_icon="search_off",
                    empty_title="No items found",
                    empty_description="Try changing your search or filters.",
                    render_footer=render_inventory_footer,
                )

            # Render table
            inventory_rows()
