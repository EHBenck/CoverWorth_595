from nicegui import ui
from utilities.nav_wrapper import build_app_shell
from utilities.inventory_table import add_view_mode_toggle, render_data_table



# COVERWORTH - INVENTORY PAGE
# ------------------------------------------------------------
# Mock data is used for now.
# Later will be replaced with live backend data.



INVENTORY_ITEMS = [
    {
        "id": 1,
        "name": "Canon EOS R6",
        "category": "Electronics",
        "location": "Office",
        "estimated_value": 1850,
        "status": "Current",
        "icon": "photo_camera",
    },
    {
        "id": 2,
        "name": "Seiko Prospex",
        "category": "Watches",
        "location": "Bedroom",
        "estimated_value": 725,
        "status": "Review",
        "icon": "watch",
    },
    {
        "id": 3,
        "name": "MacBook Pro",
        "category": "Electronics",
        "location": "Office",
        "estimated_value": 1250,
        "status": "Current",
        "icon": "laptop_mac",
    },
    {
        "id": 4,
        "name": "Lake Painting",
        "category": "Art",
        "location": "Living Room",
        "estimated_value": 475,
        "status": "Current",
        "icon": "image",
    },
    {
        "id": 5,
        "name": "Leather Couch",
        "category": "Furniture",
        "location": "Living Room",
        "estimated_value": 2100,
        "status": "Current",
        "icon": "chair",
    },
    {
        "id": 6,
        "name": "Titleist Golf Clubs",
        "category": "Sports",
        "location": "Garage",
        "estimated_value": 850,
        "status": "Review",
        "icon": "sports_golf",
    },
    {
        "id": 7,
        "name": "Vintage Record Player",
        "category": "Collectibles",
        "location": "Living Room",
        "estimated_value": 620,
        "status": "Current",
        "icon": "album",
    },
    {
        "id": 8,
        "name": "Hiking Backpack",
        "category": "Outdoor",
        "location": "Garage",
        "estimated_value": 220,
        "status": "Current",
        "icon": "backpack",
    },
]



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



# INVENTORY PAGE
@ui.page("/inventory")
def inventory_page():

    ui.page_title(
        "Inventory | CoverWorth"
    )

    build_app_shell("Inventory")


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
                on_click=lambda:
                ui.notify(
                    "Add Item page will be connected later."
                ),
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
                category_filter = ui.select(
                    [
                        "All Categories",
                        "Electronics",
                        "Watches",
                        "Art",
                        "Furniture",
                        "Sports",
                        "Collectibles",
                        "Outdoor",
                    ],
                    value="All Categories",
                    on_change=lambda _:
                    refresh_inventory(),
                ).props(
                    "outlined dense"
                ).classes(
                    "filter-control w-[190px]"
                )

                # LOCATION FILTER
                location_filter = ui.select(
                    [
                        "All Locations",
                        "Office",
                        "Bedroom",
                        "Living Room",
                        "Garage",
                    ],
                    value="All Locations",
                    on_change=lambda _:
                    refresh_inventory(),
                ).props(
                    "outlined dense"
                ).classes(
                    "filter-control w-[190px]"
                )

                # STATUS FILTER
                status_filter = ui.select(
                    [
                        "All Statuses",
                        "Current",
                        "Review",
                    ],
                    value="All Statuses",
                    on_change=lambda _:
                    refresh_inventory(),
                ).props(
                    "outlined dense"
                ).classes(
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

                for item in INVENTORY_ITEMS:

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
                            f"of {len(INVENTORY_ITEMS)} items"
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
