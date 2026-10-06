from urllib.parse import quote

from nicegui import ui

from utilities.mockdata import CATEGORY_SUMMARIES
from utilities.nav_wrapper import build_app_shell


# ============================================================
# COVERWORTH - CATEGORIES PAGE
# ------------------------------------------------------------
# Current implementation:
#   - Uses shared mock data
#   - Supports search
#   - Supports sorting
#   - Supports temporary Create / Edit / Delete interactions
#
# TODO:
#   - Replace local category mutations with Django API calls
#   - Load category summaries from backend
#   - Connect inventory filtering by category public_id
# ============================================================


# ============================================================
# STYLING
# ============================================================

ui.add_css("""
    body {
        background: #f3f8fb;
        color: #0f172a;
        font-family: Inter, Roboto, Arial, sans-serif;
    }

    .nicegui-content {
        padding: 0 !important;
        background-color: #f3f8fb !important;
    }


    /* ========================================================
       CATEGORIES PAGE
       ======================================================== */

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


    /* ========================================================
       FILTER CONTROLS
       ======================================================== */

    .category-filter-control .q-field__control {
        min-height: 52px;
    }


    /* ========================================================
       CATEGORY GRID
       ======================================================== */

    .category-grid {
        display: grid;
        grid-template-columns:
            repeat(3, minmax(0, 1fr));

        width: 100%;
        gap: 16px;
    }


    /* ========================================================
       CATEGORY CARD
       ======================================================== */

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


    /* ========================================================
       CATEGORY ICON
       ======================================================== */

    .category-icon-box {
        width: 96px;
        height: 96px;

        border-radius: 18px;

        display: flex;
        align-items: center;
        justify-content: center;

        flex-shrink: 0;
    }


    /* ========================================================
       CARD TEXT
       ======================================================== */

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


    /* ========================================================
       ABOUT CATEGORIES
       ======================================================== */

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


    /* ========================================================
       EMPTY STATE
       ======================================================== */

    .category-empty {
        min-height: 280px;
    }


    /* ========================================================
       DIALOG
       ======================================================== */

    .category-dialog-card {
        width: 520px;
        max-width: calc(100vw - 32px);

        border-radius: 12px;
    }


    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 1150px) {
        .category-grid {
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 750px) {
        .category-grid {
            grid-template-columns:
                1fr;
        }

        .category-icon-box {
            width: 78px;
            height: 78px;
        }
    }
""", shared=True)


# ============================================================
# CATEGORIES PAGE
# ============================================================

@ui.page("/categories")
def categories_page():

    ui.page_title(
        "Categories | CoverWorth"
    )

    build_app_shell(
        "Categories"
    )


    # --------------------------------------------------------
    # Make a page-local copy of the mock records.
    #
    # This lets Create/Edit/Delete work during the current
    # browser session without changing utilities/mockdata.py.
    #
    # Later this will come from Django instead.
    # --------------------------------------------------------

    categories = [
        category.copy()
        for category in CATEGORY_SUMMARIES
    ]

    editing_category_id = {
        "value": None
    }


    # ========================================================
    # CREATE / EDIT CATEGORY DIALOG
    # ========================================================

    with ui.dialog() as category_dialog:

        with ui.card().classes(
            "category-dialog-card p-6 gap-5"
        ):

            with ui.column().classes(
                "gap-0"
            ):

                dialog_title = ui.label(
                    "Create Category"
                ).classes(
                    "text-2xl font-bold"
                )

                dialog_subtitle = ui.label(
                    "Create a category to organize your inventory."
                ).classes(
                    "text-sm muted"
                )


            category_name_input = ui.input(
                label="Category Name",
                placeholder="Example: Photography Gear",
            ).props(
                "outlined"
            ).classes(
                "w-full"
            )


            category_description_input = ui.textarea(
                label="Description",
                placeholder=(
                    "Add an optional description "
                    "for this category..."
                ),
            ).props(
                "outlined autogrow"
            ).classes(
                "w-full"
            )


            dialog_error = ui.label().classes(
                "text-sm text-red-600"
            )


            def close_category_dialog():

                category_dialog.close()

                category_name_input.value = ""
                category_description_input.value = ""

                editing_category_id["value"] = None

                dialog_error.text = ""


            def save_category():

                name = (
                    category_name_input.value or ""
                ).strip()

                description = (
                    category_description_input.value or ""
                ).strip()


                # --------------------------------------------
                # VALIDATION
                # --------------------------------------------

                if not name:

                    dialog_error.text = (
                        "Category name is required."
                    )

                    return


                duplicate = next(
                    (
                        category
                        for category in categories
                        if (
                            category["name"].lower()
                            == name.lower()
                            and category["id"]
                            != editing_category_id["value"]
                        )
                    ),
                    None,
                )


                if duplicate:

                    dialog_error.text = (
                        "A category with this name "
                        "already exists."
                    )

                    return


                # --------------------------------------------
                # CREATE
                # --------------------------------------------

                if editing_category_id["value"] is None:

                    next_id = (
                        max(
                            (
                                category["id"]
                                for category in categories
                            ),
                            default=0,
                        )
                        + 1
                    )


                    categories.append(
                        {
                            "id": next_id,
                            "name": name,
                            "description": description,
                            "item_count": 0,
                            "total_value": 0,
                            "updated": "Updated just now",
                            "updated_days": 0,
                            "icon": "category",
                            "icon_background": "#dbeafe",
                            "icon_color": "#1d4ed8",
                        }
                    )


                    ui.notify(
                        f'Category "{name}" created.',
                        type="positive",
                    )


                # --------------------------------------------
                # EDIT
                # --------------------------------------------

                else:

                    category = next(
                        (
                            category
                            for category in categories
                            if category["id"]
                            == editing_category_id["value"]
                        ),
                        None,
                    )


                    if category:

                        category["name"] = name

                        category["description"] = (
                            description
                        )

                        category["updated"] = (
                            "Updated just now"
                        )

                        category["updated_days"] = 0


                        ui.notify(
                            f'Category "{name}" updated.',
                            type="positive",
                        )


                close_category_dialog()

                category_grid.refresh()


            with ui.row().classes(
                "w-full "
                "items-center "
                "justify-end "
                "gap-3"
            ):

                ui.button(
                    "Cancel",
                    on_click=close_category_dialog,
                ).props(
                    "flat "
                    "color=grey-7 "
                    "no-caps"
                )


                ui.button(
                    "Save Category",
                    icon="check",
                    on_click=save_category,
                ).props(
                    "unelevated "
                    "color=primary "
                    "no-caps"
                ).classes(
                    "px-5"
                )


    # ========================================================
    # OPEN CREATE DIALOG
    # ========================================================

    def open_create_category():

        editing_category_id["value"] = None

        dialog_title.text = (
            "Create Category"
        )

        dialog_subtitle.text = (
            "Create a category to organize your inventory."
        )

        category_name_input.value = ""

        category_description_input.value = ""

        dialog_error.text = ""

        category_dialog.open()


    # ========================================================
    # OPEN EDIT DIALOG
    # ========================================================

    def open_edit_category(category):

        editing_category_id["value"] = (
            category["id"]
        )

        dialog_title.text = (
            "Edit Category"
        )

        dialog_subtitle.text = (
            "Update this category's name or description."
        )

        category_name_input.value = (
            category["name"]
        )

        category_description_input.value = (
            category.get(
                "description",
                "",
            )
        )

        dialog_error.text = ""

        category_dialog.open()


    # ========================================================
    # DELETE CATEGORY
    # ========================================================

    def open_delete_dialog(category):

        with ui.dialog() as delete_dialog:

            with ui.card().classes(
                "w-[460px] "
                "max-w-[calc(100vw-32px)] "
                "p-6 gap-5"
            ):

                with ui.row().classes(
                    "items-center gap-3"
                ):

                    ui.icon(
                        "warning_amber"
                    ).classes(
                        "text-3xl text-red-600"
                    )

                    with ui.column().classes(
                        "gap-0"
                    ):

                        ui.label(
                            f'Delete {category["name"]}?'
                        ).classes(
                            "text-xl font-bold"
                        )

                        ui.label(
                            (
                                f'{category["item_count"]} '
                                "items currently use "
                                "this category."
                            )
                        ).classes(
                            "text-sm muted"
                        )


                ui.label(
                    (
                        "This frontend prototype will remove "
                        "the category from this page only. "
                        "Database deletion will be handled "
                        "when the category API is implemented."
                    )
                ).classes(
                    "text-sm text-slate-700"
                )


                def delete_category():

                    categories[:] = [
                        existing
                        for existing in categories
                        if existing["id"]
                        != category["id"]
                    ]

                    delete_dialog.close()

                    category_grid.refresh()

                    ui.notify(
                        (
                            f'{category["name"]} '
                            "removed from the prototype."
                        ),
                        type="warning",
                    )


                with ui.row().classes(
                    "w-full "
                    "justify-end "
                    "gap-3"
                ):

                    ui.button(
                        "Cancel",
                        on_click=delete_dialog.close,
                    ).props(
                        "flat "
                        "color=grey-7 "
                        "no-caps"
                    )


                    ui.button(
                        "Delete Category",
                        icon="delete",
                        on_click=delete_category,
                    ).props(
                        "unelevated "
                        "color=negative "
                        "no-caps"
                    )


        delete_dialog.open()


    # ========================================================
    # MAIN PAGE CONTENT
    # ========================================================

    with ui.column().classes(
        "categories-container "
        "page-content-frame "
        "p-7 gap-5"
    ):


        # ====================================================
        # PAGE HEADER
        # ====================================================

        with ui.row().classes(
            "w-full "
            "items-center "
            "justify-between"
        ):


            with ui.column().classes(
                "gap-0"
            ):

                ui.label(
                    "Categories"
                ).classes(
                    "text-4xl "
                    "font-bold "
                    "tracking-tight"
                )

                ui.label(
                    "Organize your inventory by category"
                ).classes(
                    "text-base muted"
                )


            ui.button(
                "New Category",
                icon="add",
                on_click=open_create_category,
            ).props(
                "unelevated "
                "color=primary "
                "no-caps"
            ).classes(
                "px-5 py-2 rounded-lg"
            )


        # ====================================================
        # CATEGORY PANEL
        # ====================================================

        with ui.card().classes(
            "categories-panel "
            "w-full "
            "p-4 gap-5"
        ):


            # =================================================
            # SEARCH / SORT
            # =================================================

            with ui.row().classes(
                "w-full "
                "items-center "
                "gap-4 "
                "flex-wrap"
            ):


                def refresh_categories():

                    category_grid.refresh()


                search_input = ui.input(
                    placeholder="Search categories...",
                    on_change=lambda _:
                    refresh_categories(),
                ).props(
                    "outlined "
                    "prepend-icon=search "
                    "clearable"
                ).classes(
                    "category-filter-control "
                    "min-w-[300px] "
                    "flex-1"
                )


                with ui.row().classes("items-center gap-2"):
                    ui.label("Sort by").classes("text-sm muted")
                    sort_filter = ui.select(
                        [
                            "Value",
                            "Name",
                            "Item Count",
                            "Recently Updated",
                        ],
                        value="Value",
                        on_change=lambda _:
                        refresh_categories(),
                    ).props(
                        "outlined options-dense"
                    ).classes(
                        "category-filter-control "
                        "w-[210px]"
                    )


            # =================================================
            # CATEGORY GRID
            # =================================================

            @ui.refreshable
            def category_grid():

                search_text = (
                    search_input.value or ""
                ).strip().lower()


                filtered_categories = [
                    category
                    for category in categories
                    if (
                        not search_text
                        or search_text
                        in category["name"].lower()
                        or search_text
                        in category.get(
                            "description",
                            "",
                        ).lower()
                    )
                ]


                # --------------------------------------------
                # SORTING
                # --------------------------------------------

                if sort_filter.value == "Value":

                    filtered_categories.sort(
                        key=lambda category:
                        category["total_value"],
                        reverse=True,
                    )


                elif sort_filter.value == "Name":

                    filtered_categories.sort(
                        key=lambda category:
                        category["name"].lower()
                    )


                elif sort_filter.value == "Item Count":

                    filtered_categories.sort(
                        key=lambda category:
                        category["item_count"],
                        reverse=True,
                    )


                elif sort_filter.value == "Recently Updated":

                    filtered_categories.sort(
                        key=lambda category:
                        category["updated_days"]
                    )


                # --------------------------------------------
                # EMPTY STATE
                # --------------------------------------------

                if not filtered_categories:

                    with ui.column().classes(
                        "category-empty "
                        "w-full "
                        "items-center "
                        "justify-center "
                        "gap-2"
                    ):

                        ui.icon(
                            "category"
                        ).classes(
                            "text-6xl "
                            "text-slate-300"
                        )

                        ui.label(
                            "No categories found"
                        ).classes(
                            "text-lg "
                            "font-semibold "
                            "text-slate-600"
                        )

                        ui.label(
                            (
                                "Try changing your search "
                                "or create a new category."
                            )
                        ).classes(
                            "text-sm muted"
                        )

                    return


                # --------------------------------------------
                # CARDS
                # --------------------------------------------

                with ui.element(
                    "div"
                ).classes(
                    "category-grid"
                ):


                    for category in filtered_categories:

                        with ui.card().classes(
                            "category-card "
                            "w-full "
                            "p-5 gap-4"
                        ):


                            # =================================
                            # CARD TOP
                            # =================================

                            with ui.row().classes(
                                "w-full "
                                "items-start "
                                "gap-4 "
                                "flex-nowrap"
                            ):


                                # -----------------------------
                                # ICON
                                # -----------------------------

                                with ui.element(
                                    "div"
                                ).classes(
                                    "category-icon-box"
                                ).style(
                                    (
                                        "background: "
                                        f'{category["icon_background"]};'
                                    )
                                ):

                                    ui.icon(
                                        category["icon"]
                                    ).classes(
                                        "text-5xl"
                                    ).style(
                                        (
                                            "color: "
                                            f'{category["icon_color"]};'
                                        )
                                    )


                                # -----------------------------
                                # CATEGORY INFO
                                # -----------------------------

                                with ui.column().classes(
                                    "gap-1 flex-1"
                                ):

                                    ui.label(
                                        category["name"]
                                    ).classes(
                                        "category-name"
                                    )

                                    ui.label(
                                        (
                                            f'{category["item_count"]:,} '
                                            "items"
                                        )
                                    ).classes(
                                        "category-count"
                                    )

                                    ui.label(
                                        (
                                            f'${category["total_value"]:,.0f}'
                                        )
                                    ).classes(
                                        "category-value mt-1"
                                    )


                                    with ui.row().classes(
                                        "items-center "
                                        "gap-2 mt-1"
                                    ):

                                        ui.icon(
                                            "schedule"
                                        ).classes(
                                            "text-[18px] "
                                            "text-slate-500"
                                        )

                                        ui.label(
                                            category["updated"]
                                        ).classes(
                                            "category-updated"
                                        )


                                # -----------------------------
                                # ACTION MENU
                                # -----------------------------

                                with ui.button(
                                    icon="more_vert"
                                ).props(
                                    "flat "
                                    "round "
                                    "dense "
                                    "color=grey-9"
                                ):

                                    with ui.menu():

                                        ui.menu_item(
                                            "Edit Category",
                                            on_click=(
                                                lambda category=category:
                                                open_edit_category(
                                                    category
                                                )
                                            ),
                                        )


                                        ui.menu_item(
                                            "View Items",
                                            on_click=(
                                                lambda category=category:
                                                ui.navigate.to(
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
                                                lambda category=category:
                                                open_delete_dialog(
                                                    category
                                                )
                                            ),
                                        )


                            # =================================
                            # CARD FOOTER
                            # =================================

                            ui.separator()


                            ui.button(
                                "View Items",
                                icon="arrow_forward",
                                on_click=(
                                    lambda category=category:
                                    ui.navigate.to(
                                        (
                                            "/inventory"
                                            "?category="
                                            f'{quote(category["name"])}'
                                        )
                                    )
                                ),
                            ).props(
                                "flat "
                                "color=primary "
                                "no-caps "
                                "icon-right"
                            ).classes(
                                "self-start "
                                "font-semibold"
                            )


            category_grid()


            # =================================================
            # ABOUT CATEGORIES
            # =================================================

            with ui.row().classes(
                "about-categories "
                "items-center "
                "gap-4 "
                "p-4 "
                "flex-nowrap"
            ):


                with ui.element(
                    "div"
                ).classes(
                    "about-icon"
                ):

                    ui.icon(
                        "info"
                    ).classes(
                        "text-xl"
                    )


                with ui.column().classes(
                    "gap-0"
                ):

                    ui.label(
                        "About Categories"
                    ).classes(
                        "text-base "
                        "font-semibold "
                        "text-slate-900"
                    )

                    ui.label(
                        (
                            "Categories help you organize your "
                            "inventory items. You'll select a "
                            "category when adding new items, "
                            "and you can use categories to "
                            "filter and view your inventory."
                        )
                    ).classes(
                        "text-sm text-slate-600"
                    )