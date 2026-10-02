from nicegui import ui



# COVERWORTH - INVENTORY PAGE
# ------------------------------------------------------------
# Mock data is used for now.
# Later this can be replaced with data returned by Django.



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
       SIDEBAR
       ======================================================== */

    .sidebar {
        background: linear-gradient(
            180deg,
            #173653 0%,
            #183c5d 100%
        );

        color: white;
    }

    .sidebar-logo {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    .nav-item {
        width: 100%;
        min-height: 48px;

        border-radius: 8px;

        color: #dbeafe;

        padding: 0 14px;

        cursor: pointer;
    }

    .nav-item:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .nav-item-active {
        background: #1769c2;
        color: white;
    }


    /* ========================================================
       HEADER
       ======================================================== */

    .top-header {
        background: white;
        color: #0f172a;

        border-bottom: 1px solid #dce3ec;

        box-shadow: none;
    }


    /* ========================================================
       INVENTORY PAGE
       ======================================================== */

    .inventory-container {
        width: 100%;
        max-width: 1500px;

        margin: 0 auto;
    }

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


    /* ========================================================
       TABLE WRAPPER
       ======================================================== */

    .inventory-table-wrapper {
        width: 100%;
        overflow-x: auto;
    }

    .inventory-table {
        width: 100%;
        min-width: 1000px;
    }


    /* ========================================================
       TABLE GRID

       Columns:
       1. Checkbox
       2. Image
       3. Item Name
       4. Category
       5. Estimated Value
       6. Status
       7. Actions
       ======================================================== */

    .inventory-grid {
        display: grid !important;

        grid-template-columns:
            50px
            75px
            minmax(200px, 1.8fr)
            minmax(140px, 1fr)
            minmax(150px, 1fr)
            minmax(120px, 0.8fr)
            70px !important;

        align-items: center !important;

        width: 100%;
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
       TABLE HEADER
       ======================================================== */

    .table-header {
        min-height: 52px;

        padding: 0 12px;

        background: #f8fafc;

        border-bottom: 1px solid #e2e8f0;

        color: #475569;

        font-size: 13px;
        font-weight: 600;
    }

    .table-header > * {
        min-width: 0;
    }


    /* ========================================================
       TABLE ROWS
       ======================================================== */

    .inventory-row {
        min-height: 76px;

        padding: 0 12px;

        border-bottom: 1px solid #e2e8f0;

        transition:
            background-color 0.15s ease;
    }

    .inventory-row:hover {
        background: #f8fafc;
    }

    .inventory-row > * {
        min-width: 0;
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



# NAVIGATION COMPONENT


def navigation_item(
    label: str,
    icon: str,
    route: str | None = None,
    active: bool = False,
) -> None:

    classes = "nav-item items-center gap-3"

    if active:
        classes += " nav-item-active"

    def navigate():

        if route:
            ui.navigate.to(route)

        else:
            ui.notify(
                f"{label} page has not been implemented yet."
            )

    with ui.row().classes(
        classes
    ).on(
        "click",
        navigate,
    ):

        ui.icon(
            icon
        ).classes(
            "text-xl"
        )

        ui.label(
            label
        ).classes(
            "text-sm font-medium"
        )



# INVENTORY PAGE


@ui.page("/inventory")
def inventory_page():

    ui.page_title(
        "Inventory | CoverWorth"
    )

    view_mode = {"value": "grid"}


    
    # SIDEBAR
    

    with ui.left_drawer(
        value=True,
        top_corner=True,
        bottom_corner=True,
    ).props(
        "width=230 breakpoint=800"
    ).classes(
        "sidebar p-0"
    ) as drawer:


        # ----------------------------------------------------
        # LOGO
        # ----------------------------------------------------

        with ui.row().classes(
            "w-full items-center gap-3 px-5 py-6"
        ):

            with ui.element(
                "div"
            ).classes(
                "w-10 h-10 "
                "bg-blue-500/20 "
                "rounded-xl "
                "flex items-center "
                "justify-center"
            ):

                ui.icon(
                    "inventory_2"
                ).classes(
                    "text-3xl text-blue-400"
                )

            ui.label(
                "CoverWorth"
            ).classes(
                "sidebar-logo"
            )


        # ----------------------------------------------------
        # NAVIGATION
        # ----------------------------------------------------

        with ui.column().classes(
            "w-full px-3 gap-2"
        ):

            navigation_item(
                "Dashboard",
                "home",
                route="/",
            )

            navigation_item(
                "Inventory",
                "inventory_2",
                route="/inventory",
                active=True,
            )

            navigation_item(
                "Collections",
                "folder",
            )

            navigation_item(
                "Valuations",
                "analytics",
            )

            navigation_item(
                "Reports",
                "description",
            )

            ui.separator().classes(
                "my-3 opacity-20"
            )

            navigation_item(
                "Settings",
                "settings",
            )


    
    # TOP HEADER
    

    with ui.header().classes(
        "top-header h-[68px] "
        "items-center px-5"
    ):

        ui.button(
            icon="menu",
            on_click=drawer.toggle,
        ).props(
            "flat round color=grey-8"
        )

        ui.space()

        ui.input(
            placeholder=(
                "Search items, categories, or locations..."
            )
        ).props(
            "outlined dense rounded "
            "prepend-icon=search"
        ).classes(
            "w-[520px] max-w-[50vw]"
        )

        ui.space()

        ui.button(
            icon="notifications_none"
        ).props(
            "flat round color=grey-8"
        )

        ui.avatar(
            "KM",
            color="primary",
            text_color="white",
        ).classes(
            "ml-2"
        )

        ui.label(
            "Kevin M."
        ).classes(
            "font-medium hidden md:block"
        )

        ui.button(
            icon="keyboard_arrow_down"
        ).props(
            "flat round dense color=grey-8"
        )


    
    # MAIN PAGE CONTENT
    

    with ui.column().classes(
        "inventory-container p-7 gap-5"
    ):


        # ----------------------------------------------------
        # PAGE TITLE
        # ----------------------------------------------------

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


                def set_view_mode(mode: str):
                    view_mode["value"] = mode
                    list_view_button.props(
                        "outline color=primary"
                        if mode == "list"
                        else "flat color=grey-8"
                    )
                    grid_view_button.props(
                        "outline color=primary"
                        if mode == "grid"
                        else "flat color=grey-8"
                    )
                    refresh_inventory()


                # ---------------------------------------------
                # SEARCH
                # ---------------------------------------------

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


                # ---------------------------------------------
                # CATEGORY FILTER
                # ---------------------------------------------

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


                # ---------------------------------------------
                # LOCATION FILTER
                # ---------------------------------------------

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


                # ---------------------------------------------
                # STATUS FILTER
                # ---------------------------------------------

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


                # ---------------------------------------------
                # LIST / GRID VIEW
                # ---------------------------------------------

                with ui.button_group().props(
                    "flat"
                ):

                    list_view_button = ui.button(
                        icon="view_list",
                        on_click=lambda: set_view_mode("list"),
                    ).props(
                        "outline color=primary"
                        if view_mode["value"] == "list"
                        else "flat color=grey-8"
                    ).tooltip(
                        "List view"
                    )

                    grid_view_button = ui.button(
                        icon="grid_view",
                        on_click=lambda: set_view_mode("grid"),
                    ).props(
                        "outline color=primary"
                        if view_mode["value"] == "grid"
                        else "flat color=grey-8"
                    ).tooltip(
                        "Grid view"
                    )


            
            # INVENTORY TABLE
            

            @ui.refreshable
            def inventory_rows():

                # ---------------------------------------------
                # CURRENT FILTER VALUES
                # ---------------------------------------------

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


                # ---------------------------------------------
                # FILTER ITEMS
                # ---------------------------------------------

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


                
                # TABLE WRAPPER
                

                with ui.element(
                    "div"
                ).classes(
                    "inventory-table-wrapper"
                ):

                    with ui.element(
                        "div"
                    ).classes(
                        "inventory-table "
                        + ("grid-view" if view_mode["value"] == "grid" else "")
                    ):

                        # TABLE HEADER
                        with ui.element(
                            "div"
                        ).classes(
                            "inventory-grid "
                            "table-header"
                        ):

                            # Checkbox
                            ui.checkbox()

                            # Image
                            ui.label(
                                "Image"
                            )

                            # Item name
                            with ui.row().classes(
                                "items-center gap-1"
                            ):

                                ui.label(
                                    "Item Name"
                                )

                                ui.icon(
                                    "arrow_upward"
                                ).classes(
                                    "text-sm "
                                    "text-blue-600"
                                )

                            # Category
                            ui.label(
                                "Category"
                            )

                            # Value
                            with ui.row().classes(
                                "items-center gap-1"
                            ):

                                ui.label(
                                    "Estimated Value"
                                )

                                ui.icon(
                                    "unfold_more"
                                ).classes(
                                    "text-sm"
                                )

                            # Status
                            ui.label(
                                "Status"
                            )

                            # Actions
                            ui.label(
                                "Actions"
                            )


                        
                        # EMPTY STATE
                        

                        if not filtered_items:

                            with ui.column().classes(
                                "w-full "
                                "items-center "
                                "justify-center "
                                "py-16 "
                                "gap-2"
                            ):

                                ui.icon(
                                    "search_off"
                                ).classes(
                                    "text-5xl "
                                    "text-slate-300"
                                )

                                ui.label(
                                    "No items found"
                                ).classes(
                                    "text-lg "
                                    "font-semibold "
                                    "text-slate-600"
                                )

                                ui.label(
                                    "Try changing your "
                                    "search or filters."
                                ).classes(
                                    "text-sm muted"
                                )


                        
                        # INVENTORY ROWS
                        

                        for item in filtered_items:

                            with ui.element(
                                "div"
                            ).classes(
                                "inventory-grid "
                                "inventory-row"
                            ):


                                # --------------------------------
                                # CHECKBOX
                                # --------------------------------

                                ui.checkbox()


                                # --------------------------------
                                # IMAGE / ICON
                                # --------------------------------

                                with ui.element(
                                    "div"
                                ).classes(
                                    "item-icon"
                                ):

                                    ui.icon(
                                        item["icon"]
                                    ).classes(
                                        "text-2xl "
                                        "text-slate-600"
                                    )


                                # --------------------------------
                                # ITEM NAME
                                # --------------------------------

                                ui.label(
                                    item["name"]
                                ).classes(
                                    "text-sm "
                                    "font-semibold"
                                )


                                # --------------------------------
                                # CATEGORY
                                # --------------------------------

                                ui.label(
                                    item["category"]
                                ).classes(
                                    "text-sm "
                                    "text-slate-700"
                                )


                                # --------------------------------
                                # ESTIMATED VALUE
                                # --------------------------------

                                ui.label(
                                    f'${item["estimated_value"]:,.0f}'
                                ).classes(
                                    "text-sm "
                                    "font-medium"
                                )


                                # --------------------------------
                                # STATUS
                                # --------------------------------

                                if (
                                    item["status"]
                                    == "Current"
                                ):

                                    ui.label(
                                        "Current"
                                    ).classes(
                                        "status-current"
                                    )

                                else:

                                    ui.label(
                                        "Review"
                                    ).classes(
                                        "status-review"
                                    )


                                # --------------------------------
                                # ACTION MENU
                                # --------------------------------

                                with ui.button(
                                    icon="more_vert"
                                ).props(
                                    "flat "
                                    "round "
                                    "dense "
                                    "color=grey-8"
                                ):

                                    with ui.menu():

                                        ui.menu_item(
                                            "View Item",
                                            on_click=(
                                                lambda item=item:
                                                ui.notify(
                                                    f'View '
                                                    f'{item["name"]}'
                                                )
                                            ),
                                        )

                                        ui.menu_item(
                                            "Edit",
                                            on_click=(
                                                lambda item=item:
                                                ui.notify(
                                                    f'Edit '
                                                    f'{item["name"]}'
                                                )
                                            ),
                                        )

                                        ui.separator()

                                        ui.menu_item(
                                            "Delete",
                                            on_click=(
                                                lambda item=item:
                                                ui.notify(
                                                    f'Delete '
                                                    f'{item["name"]}'
                                                )
                                            ),
                                        )


                
                # TABLE FOOTER
                

                with ui.row().classes(
                    "table-footer "
                    "items-center "
                    "justify-between"
                ):

                    ui.label(
                        f"Showing "
                        f"{len(filtered_items)} "
                        f"of "
                        f"{len(INVENTORY_ITEMS)} "
                        f"items"
                    ).classes(
                        "text-sm muted"
                    )


                    with ui.row().classes(
                        "items-center gap-4"
                    ):

                        ui.label(
                            "Rows per page:"
                        ).classes(
                            "text-sm muted"
                        )


                        ui.select(
                            [
                                8,
                                16,
                                24,
                            ],
                            value=8,
                        ).props(
                            "dense borderless"
                        ).classes(
                            "w-16"
                        )


                        if filtered_items:

                            ui.label(
                                f"1–"
                                f"{len(filtered_items)} "
                                f"of "
                                f"{len(filtered_items)}"
                            ).classes(
                                "text-sm"
                            )

                        else:

                            ui.label(
                                "0 of 0"
                            ).classes(
                                "text-sm"
                            )


                        ui.button(
                            icon="chevron_left"
                        ).props(
                            "flat "
                            "round "
                            "disable "
                            "color=grey-6"
                        )


                        ui.button(
                            icon="chevron_right",
                            on_click=lambda:
                            ui.notify(
                                "Pagination will become "
                                "active when more data "
                                "is loaded."
                            ),
                        ).props(
                            "flat "
                            "round "
                            "color=primary"
                        )


            # Render table
            inventory_rows()
