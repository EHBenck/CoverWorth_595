import requests
from nicegui import app, ui, run
from backend_client import BACKEND_URL, authenticated_session, csrf_headers
from utilities.nav_wrapper import build_app_shell
from utilities.inventory_table import add_view_mode_toggle, render_data_table
from utilities.mockdata import AI_PREVIEW, VALUATION_ITEMS


# ============================================================
# COVERWORTH - VALUATIONS PAGE
# ------------------------------------------------------------
# Uses mock data for the frontend implementation.
#
# TODO:
#   - valuation rows can come from the Django API
#   - "Update" can trigger a valuation endpoint
#   - AI Valuation Preview can display real market data
# ============================================================


# ============================================================
# CSS
# ============================================================

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
       PAGE
       ======================================================== */

    .valuations-card {
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
       VALUATION TABS
       ======================================================== */

    .valuation-tabs {
        border-bottom: 1px solid #e2e8f0;
    }

    .valuation-tabs .q-tab {
        text-transform: none;
        font-weight: 500;
        min-height: 50px;
    }

    .valuation-tabs .q-tab--active {
        font-weight: 600;
    }


    /* ========================================================
       FILTERS
       ======================================================== */

    .filter-control .q-field__control {
        min-height: 44px;
    }


    /* ========================================================
       ITEM IMAGE PLACEHOLDER
       ======================================================== */

    .valuation-item-icon {
        width: 48px;
        height: 48px;

        background: #f1f5f9;

        border-radius: 8px;

        display: flex;
        align-items: center;
        justify-content: center;

        flex-shrink: 0;
    }

    .data-table.valuation-table.grid-view {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        min-width: 0;
    }

    .data-table.valuation-table.grid-view .data-table-header {
        display: none !important;
    }

    .data-table.valuation-table.grid-view .data-table-row {
        grid-template-columns: 32px minmax(0, 1fr) minmax(0, 1fr) !important;
        grid-template-areas:
            "check item item"
            "value value updated"
            "status actions actions";
        gap: 12px;
        align-items: center;
    }

    .data-table.valuation-table.grid-view .valuation-item-cell {
        grid-area: item;
    }

    .data-table.valuation-table.grid-view .valuation-current-value-cell {
        grid-area: value;
        font-size: 18px;
        font-weight: 700;
    }

    .data-table.valuation-table.grid-view .valuation-updated-cell {
        grid-area: updated;
    }

    .data-table.valuation-table.grid-view .data-table-row > :nth-child(1) {
        grid-area: check;
    }

    .data-table.valuation-table.grid-view .data-table-row > :nth-child(5) {
        grid-area: status;
    }

    .data-table.valuation-table.grid-view .data-table-row > :nth-child(6) {
        grid-area: actions;
        justify-self: end;
    }


    /* ========================================================
       STATUS BADGES
       ======================================================== */

    .valuation-current {
        display: inline-block;

        width: fit-content;

        padding: 5px 12px;

        border-radius: 999px;

        background: #dcfce7;
        color: #166534;

        font-size: 12px;
        font-weight: 600;
    }

    .valuation-review {
        display: inline-block;

        width: fit-content;

        padding: 5px 12px;

        border-radius: 999px;

        background: #fee2e2;
        color: #b91c1c;

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


    /* ========================================================
       AI PREVIEW
       ======================================================== */

    .ai-preview-card {
        background: white;

        border: 1px solid #e1e7ef;
        border-radius: 12px;

        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .preview-section {
        min-width: 0;
    }

    .preview-divider {
        width: 1px;
        align-self: stretch;
        background: #e2e8f0;
    }

    .preview-image {
        width: 125px;
        height: 125px;

        border-radius: 10px;

        background: #eef2f7;

        display: flex;
        align-items: center;
        justify-content: center;

        flex-shrink: 0;
    }

    .confidence-bar {
        height: 9px;

        border-radius: 999px;

        background: #e2e8f0;

        overflow: hidden;
    }

    .confidence-fill {
        width: 82%;
        height: 100%;

        background: #16a34a;

        border-radius: 999px;
    }

    .ai-callout {
        background: #eff6ff;
        color: #1d4ed8;

        border-radius: 8px;

        padding: 12px 14px;
    }


    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 1050px) {

        .preview-content {
            flex-direction: column !important;
        }

        .preview-divider {
            width: 100%;
            height: 1px;
        }
    }
""", shared=True)

def fetch_inventory_items(cookies):
    """Load inventory items from Django."""

    if not cookies:
        raise PermissionError("Please sign in first.")

    session = authenticated_session(cookies)

    response = session.get(
        f"{BACKEND_URL}/api/items/",
        timeout=10,
    )

    if response.status_code in (401, 403):
        raise PermissionError("Please sign in again.")

    response.raise_for_status()

    return response.json().get("items", [])

def fetch_live_valuation(item_id, cookies):
    """Request a live valuation from Django."""

    if not cookies:
        raise PermissionError("Please sign in first.")

    session = authenticated_session(cookies)

    response = session.post(
        f"{BACKEND_URL}/api/item/{item_id}/valuation/",
        headers=csrf_headers(session),
        timeout=45,
    )

    if response.status_code in (401, 403):
        raise PermissionError("Your session expired or access was denied.")

    response.raise_for_status()

    return response.json()

def fetch_valuation_history(item_id, cookies):
    """Retrieve previous valuations for an inventory item."""

    if not cookies:
        raise PermissionError("Please sign in first.")

    session = authenticated_session(cookies)

    response = session.get(
        f"{BACKEND_URL}/api/item/{item_id}/valuation/history/",
        timeout=15,
    )

    if response.status_code in (401, 403):
        raise PermissionError("Your session expired or access was denied.")

    response.raise_for_status()

    return response.json()

def accept_live_valuation(item_id, valuation_run_id, cookies):
    session = authenticated_session(cookies)

    response = session.post(
        f"http://127.0.0.1:8000/api/item/{item_id}/valuation/accept/",
        json={"valuation_run_id": valuation_run_id},
        headers=csrf_headers(session),
        timeout=30,
    )

    response.raise_for_status()
    return response.json()

# ============================================================
# VALUATIONS PAGE
# ============================================================

@ui.page("/valuations")
async def valuations_page():

    ui.page_title(
        "Valuations | CoverWorth"
    )


    build_app_shell("Valuations")

    cookies = app.storage.user.get("auth_cookies")

    try:
        inventory_items = await run.io_bound(
            fetch_inventory_items,
            cookies,
        )

    except (requests.RequestException, PermissionError) as error:
        ui.notify(f"Could not load inventory: {error}", type="negative")
        inventory_items = []

    print("Inventory items from Django:", inventory_items)
    
    live_valuation = {"result": None}

    async def update_valuation(item):
        item_id = item.get("public_id")

        if not item_id:
            ui.notify(
                "This item is mock data and has no Django item ID.",
                type="warning",
            )
            return

        ui.notify(f'Fetching live valuation for {item["name"]}...')

        try:
            cookies = app.storage.user.get("auth_cookies")

            result = await run.io_bound(
                fetch_live_valuation,
                item_id,
                cookies,
            )

        except PermissionError as error:
            ui.notify(str(error), type="negative")
            return

        except requests.RequestException as error:
            ui.notify(f"Valuation request failed: {error}", type="negative")
            return

        if result.get("estimate") is not None:
            ui.notify(
                f'Live estimate: ${result["estimate"]:,.2f}',
                type="positive",
            )
        else:
            ui.notify(
                "Not enough comparable listings to calculate a valuation.",
                type="warning",
            )

        print("Live valuation result:", result)
        live_valuation["result"] = result
        valuation_preview.refresh()
  
        if result.get("estimate") is not None:
            item["current_value"] = float(result["estimate"])
            item["estimated_value"] = float(result["estimate"])
            item["status"] = "Current"
            item["days_old"] = 0
            item["last_updated"] = "Just now"

            valuation_table.refresh()

    async def show_valuation_history(item):
        item_id = item.get("public_id")

        if not item_id:
            ui.notify("This item has no Django item ID.", type="warning")
            return

        try:
            cookies = app.storage.user.get("auth_cookies")

            result = await run.io_bound(
                fetch_valuation_history,
                item_id,
                cookies,
            )

        except (requests.RequestException, PermissionError) as error:
            ui.notify(f"Could not load valuation history: {error}", type="negative")
            return

        history = result.get("history", [])

        with ui.dialog() as dialog, ui.card().classes("w-[750px] max-w-full p-5 gap-4"):

            with ui.row().classes("w-full items-center justify-between"):
                ui.label(
                    f'Valuation History — {item["name"]}'
                ).classes("text-xl font-bold")

                ui.button(
                    icon="close",
                    on_click=dialog.close,
                ).props("flat round")

            if not history:
                ui.label("No previous valuations found.")

            for valuation in history:
                estimate = valuation.get("estimate")
                date = valuation.get("requested_at", "")
                comparables = valuation.get("comparables", [])

                with ui.expansion(
                    f'${estimate:,.2f}' if estimate is not None else "No estimate",
                    icon="history",
                ).classes("w-full border rounded-lg"):

                    ui.label(f"Date: {date[:10]}")
                    ui.label(
                        f'Estimated range: '
                        f'${valuation["range_low"]:,.2f} – '
                        f'${valuation["range_high"]:,.2f}'
                    )
                    ui.label(
                        f'Comparable listings used: {valuation["sample_count"]}'
                    )

                    ui.separator()

                    if not comparables:
                        ui.label(
                            "No comparable listing evidence saved for this valuation."
                        ).classes("text-sm text-gray-500")

                    for listing in comparables:
                        with ui.row().classes(
                            "w-full items-center justify-between gap-3"
                        ):
                            with ui.column().classes("gap-1 flex-1"):
                                ui.label(
                                    listing["title"]
                                ).classes("text-sm")

                                if listing.get("url"):
                                    ui.link(
                                        "View on eBay",
                                        listing["url"],
                                        new_tab=True,
                                    ).classes("text-xs")

                            ui.label(
                                f'${listing["price"]:,.2f}'
                            ).classes("font-semibold")

            ui.button(
                "Close",
                on_click=dialog.close,
            ).props("outline color=primary")

        dialog.open()
        
    async def accept_valuation():
        result = live_valuation["result"]

        if not result or not result.get("valuation_run_id"):
            ui.notify(
                "Please update an item's valuation first.",
                type="warning",
            )
            return

        item_id = result["item_id"]
        valuation_run_id = result["valuation_run_id"]

        try:
            cookies = app.storage.user.get("auth_cookies")

            saved = await run.io_bound(
                accept_live_valuation,
                item_id,
                valuation_run_id,
                cookies,
            )

        except (requests.RequestException, PermissionError) as error:
            ui.notify(
                f"Could not save valuation: {error}",
                type="negative",
            )
            return

        if saved.get("success"):
            for item in inventory_items:
                if item["public_id"] == item_id:
                    item["estimated_value"] = saved["estimated_value"]
                    item["current_value"] = saved["estimated_value"]
                    item["status"] = "Current"
                    item["days_old"] = 0
                    item["last_updated"] = "Just now"
                    break

            valuation_table.refresh()

            ui.notify(
                f'Valuation saved: ${saved["estimated_value"]:,.2f}',
                type="positive",
            )


    from datetime import datetime, timezone

    today = datetime.now(timezone.utc)

    for item in inventory_items:
        item["icon"] = "inventory_2"
        item["category"] = item.get("category") or "Uncategorized"
        item["location"] = item.get("location") or "Unspecified"

        item["current_value"] = float(item.get("estimated_value") or 0)

        updated_at = item.get("updated_at")
        if updated_at:
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            item["days_old"] = (today - updated).days
            item["last_updated"] = f'{item["days_old"]} days ago'
        else:
            item["days_old"] = 999
            item["last_updated"] = "Never"

        item["status"] = (
            "Current" if item.get("estimated_value") is not None
            else "Needs Review"
        )

    # ========================================================
    # PAGE CONTENT
    # ========================================================

    with ui.column().classes(
        "valuations-container page-content-frame p-7 gap-5"
    ): 

        # ----------------------------------------------------
        # PAGE HEADER
        # ----------------------------------------------------

        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            with ui.column().classes(
                "gap-0"
            ):

                ui.label(
                    "Valuations"
                ).classes(
                    "text-4xl "
                    "font-bold "
                    "tracking-tight"
                )

                ui.label(
                    "Keep your inventory values up to date."
                ).classes(
                    "text-base muted"
                )


            ui.button(
                "Update All",
                icon="sync",
                on_click=lambda:
                ui.notify(
                    "Valuation update started."
                ),
            ).props(
                "unelevated "
                "color=primary "
                "no-caps"
            ).classes(
                "px-5 py-2 rounded-lg"
            )


        # ====================================================
        # VALUATION TABLE CARD
        # ====================================================

        with ui.card().classes(
            "valuations-card w-full p-0 gap-0"
        ):


            # ------------------------------------------------
            # TABS
            # ------------------------------------------------

            with ui.tabs().classes(
                "valuation-tabs w-full px-4"
            ) as tabs:

                all_tab = ui.tab(
                    "All Items (128)"
                )

                review_tab = ui.tab(
                    "Needs Review (8)"
                )

                recent_tab = ui.tab(
                    "Updated Recently (3)"
                )


            # ------------------------------------------------
            # FILTERS
            # ------------------------------------------------

            with ui.row().classes(
                "w-full "
                "items-center "
                "gap-3 "
                "flex-wrap "
                "p-4"
            ):


                def refresh_table():
                    valuation_table.refresh()

                search_input = ui.input(
                    placeholder="Search your inventory...",
                    on_change=lambda _:
                    refresh_table(),
                ).props(
                    "outlined dense "
                    "prepend-icon=search "
                    "clearable"
                ).classes(
                    "filter-control "
                    "min-w-[300px] "
                    "flex-1"
                )


                category_filter = ui.select(
                    [
                        "All Categories",
                        "Electronics",
                        "Watches",
                        "Sports",
                        "Collectibles",
                        "Furniture",
                    ],
                    value="All Categories",
                    on_change=lambda _:
                    refresh_table(),
                ).props(
                    "outlined dense"
                ).classes(
                    "filter-control w-[190px]"
                )


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
                    refresh_table(),
                ).props(
                    "outlined dense"
                ).classes(
                    "filter-control w-[190px]"
                )


                view_mode = add_view_mode_toggle(
                    lambda: valuation_table.refresh()
                )


            # =================================================
            # REFRESHABLE TABLE
            # =================================================

            @ui.refreshable
            def valuation_table():

                search_text = (
                    search_input.value or ""
                ).strip().lower()

                category = category_filter.value
                location = location_filter.value

                selected_tab = tabs.value

                filtered_items = []

                for item in inventory_items:

                    # -----------------------------------------
                    # SEARCH FILTER
                    # -----------------------------------------

                    if search_text:

                        searchable = (
                            f'{item["name"]} '
                            f'{item["category"]} '
                            f'{item["location"]}'
                        ).lower()

                        if search_text not in searchable:
                            continue


                    # -----------------------------------------
                    # CATEGORY FILTER
                    # -----------------------------------------

                    if (
                        category != "All Categories"
                        and item["category"] != category
                    ):
                        continue


                    # -----------------------------------------
                    # LOCATION FILTER
                    # -----------------------------------------

                    if (
                        location != "All Locations"
                        and item["location"] != location
                    ):
                        continue


                    # -----------------------------------------
                    # TAB FILTER
                    # -----------------------------------------

                    if (
                        selected_tab == review_tab
                        and item["status"] != "Needs Review"
                    ):
                        continue

                    if (
                        selected_tab == recent_tab
                        and item["days_old"] > 30
                    ):
                        continue


                    filtered_items.append(
                        item
                    )


                def render_valuation_header():
                    for label in ("Item", "Current Value", "Last Updated", "Status"):
                        with ui.row().classes("items-center gap-1"):
                            ui.label(label)
                            ui.icon("unfold_more").classes("text-sm")
                    ui.label("Actions")

                def render_valuation_row(item):
                    with ui.row().classes(
                        "valuation-item-cell items-center gap-3 flex-nowrap"
                    ):
                        with ui.element("div").classes("valuation-item-icon"):
                            ui.icon(item["icon"]).classes(
                                "text-2xl text-slate-600"
                            )

                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(item["name"]).classes(
                                "text-sm font-semibold"
                            )
                            ui.label(item["category"]).classes("text-xs muted")

                    ui.label(
                        f'${item["current_value"]:,.0f}'
                        if item.get("estimated_value") is not None
                        else "Not valued"
                    ).classes(
                        "valuation-current-value-cell text-sm font-semibold"
                    )
                    ui.label(item["last_updated"]).classes(
                        "valuation-updated-cell text-sm text-slate-600"
                    )

                    if item["status"] == "Current":
                        ui.label("Current").classes("valuation-current")
                    else:
                        ui.label("Needs Review").classes("valuation-review")

                    with ui.row().classes("items-center gap-1"):
                        ui.button(
                            "Update",
                             on_click=lambda item=item: update_valuation(item),
                        ).props("outline color=primary dense no-caps")

                        with ui.button(icon="more_vert").props(
                            "flat round dense color=grey-8"
                        ):
                            with ui.menu():
                                ui.menu_item("View Item")
                                ui.menu_item("Valuation History", on_click=lambda item=item: show_valuation_history(item))
                                ui.menu_item("Update Valuation")

                def render_valuation_footer():
                    with ui.row().classes(
                        "table-footer items-center justify-between"
                    ):
                        ui.label(
                            f"Showing {len(filtered_items)} of 128 items"
                        ).classes("text-sm muted")

                        with ui.row().classes("items-center gap-4"):
                            ui.label("Rows per page:").classes("text-sm muted")
                            ui.select([6, 12, 24], value=6).props(
                                "dense borderless"
                            ).classes("w-16")
                            ui.label(
                                f"1–{len(filtered_items)} of 128"
                                if filtered_items
                                else "0 of 128"
                            ).classes("text-sm")
                            ui.button(icon="chevron_left").props(
                                "flat round disable color=grey-6"
                            )
                            ui.button(icon="chevron_right").props(
                                "flat round color=primary"
                            )

                render_data_table(
                    filtered_items,
                    view_mode=view_mode,
                    grid_columns=(
                        "50px minmax(260px, 2fr) minmax(145px, 1fr) "
                        "minmax(150px, 1fr) minmax(145px, 1fr) 125px"
                    ),
                    wrapper_class="valuation-table-wrapper",
                    table_class="valuation-table",
                    header_class="valuation-grid valuation-header",
                    row_class="valuation-grid valuation-row",
                    render_header=render_valuation_header,
                    render_row=render_valuation_row,
                    empty_icon="price_check",
                    empty_title="No valuations found",
                    empty_description="Try changing your search or filters.",
                    empty_padding="py-14",
                    render_footer=render_valuation_footer,
                )

            valuation_table()


            # Refresh when user changes tabs
            tabs.on_value_change(
                lambda _:
                valuation_table.refresh()
            )


        # ====================================================
        # AI VALUATION PREVIEW
        # ====================================================

        @ui.refreshable
        def valuation_preview():
            result = live_valuation["result"]

            preview = {
                "name": result["item_name"] if result else "Select an item to value",
                "estimate": result.get("estimate") if result else None,
                "range_low": result.get("range_low") if result else None,
                "range_high": result.get("range_high") if result else None,
                "confidence": result.get("confidence", "insufficient") if result else "N/A",
                "sample_count": result.get("sample_count", 0) if result else 0,
            }

            with ui.card().classes(
                "ai-preview-card "
                "w-full p-5 gap-4"
            ):


                # ------------------------------------------------
                # PREVIEW HEADER
                # ------------------------------------------------

                with ui.column().classes(
                    "gap-0"
                ):

                    ui.label(
                        "AI Valuation Preview"
                    ).classes(
                        "text-2xl font-bold"
                    )

                    ui.label(
                        "Review AI-powered estimates before "
                        "updating your item values."
                    ).classes(
                        "text-sm muted"
                    )


                # ------------------------------------------------
                # PREVIEW CONTENT
                # ------------------------------------------------

                with ui.row().classes(
                    "preview-content "
                    "w-full "
                    "items-stretch "
                    "gap-6 "
                    "flex-nowrap"
                ):


                    # =============================================
                    # ITEM / ESTIMATE
                    # =============================================

                    with ui.row().classes(
                        "preview-section "
                        "items-center "
                        "gap-5 "
                        "flex-1"
                    ):


                        with ui.element(
                            "div"
                        ).classes(
                            "preview-image"
                        ):

                            ui.icon(
                                "photo_camera"
                            ).classes(
                                "text-6xl "
                                "text-slate-600"
                            )


                        with ui.column().classes(
                            "gap-1"
                        ):

                            ui.label(
                                preview["name"]
                            ).classes(
                                "text-lg font-bold"
                            )

                            ui.label(
                                "Current estimate"
                            ).classes(
                                "text-sm muted"
                            )

                            ui.label(
                                f'${preview["estimate"]:,.2f}'
                                if preview["estimate"] is not None
                                else "Not yet valued"
                            ).classes(
                                "text-3xl font-bold"
                            )

                            ui.label(
                                "Estimated market range"
                            ).classes(
                                "text-sm muted mt-2"
                            )

                            ui.label(
                                f'${preview["range_low"]:,.2f} – ${preview["range_high"]:,.2f}'
                                if preview["range_low"] is not None
                                and preview["range_high"] is not None
                                else "No range available"
                            ).classes(
                                "text-lg "
                                "font-bold "
                                "text-blue-900"
                            )


                    # Divider
                    ui.element(
                        "div"
                    ).classes(
                        "preview-divider"
                    )


                    # =============================================
                    # MARKET SOURCES
                    # =============================================

                    with ui.column().classes(
                        "preview-section "
                        "gap-2 "
                        "flex-1"
                    ):

                        ui.label(
                            "Market sources"
                        ).classes(
                            "text-sm muted mb-1"
                        )


                        
                        with ui.row().classes(
                            "w-full "
                            "items-center "
                            "justify-between"
                        ):
                            ui.label(
                                "eBay"
                            ).classes(
                                "text-sm text-slate-700"
                            )

                            ui.label(
                                f'{preview["sample_count"]} comparable listings'
                            ).classes(
                                "text-sm font-semibold"
                            )



                    # Divider
                    ui.element(
                        "div"
                    ).classes(
                        "preview-divider"
                    )


                    # =============================================
                    # CONFIDENCE / ACCEPT
                    # =============================================

                    with ui.column().classes(
                        "preview-section "
                        "gap-3 "
                        "flex-[1.1]"
                    ):

                        ui.label(
                            "Confidence"
                        ).classes(
                            "text-sm muted"
                        )


                        with ui.row().classes(
                            "w-full "
                            "items-center "
                            "gap-3"
                        ):

                            with ui.element(
                                "div"
                            ).classes(
                                "confidence-bar flex-1"
                            ):

                                ui.element(
                                    "div"
                                ).classes(
                                    "confidence-fill"
                                )

                            ui.label(
                                preview["confidence"].title()
                            ).classes(
                                "text-sm "
                                "font-semibold "
                                "text-green-700"
                            )

                        # AI explanation
                        with ui.row().classes(
                            "ai-callout "
                            "w-full "
                            "items-center "
                            "gap-3"
                        ):

                            ui.icon(
                                "auto_awesome"
                            ).classes(
                                "text-2xl"
                            )

                            ui.label(
                                f'Estimate based on {preview["sample_count"]} '
                                "comparable eBay listings."
                            ).classes(
                                "text-sm"
                            )


                        # Buttons
                        with ui.row().classes(
                            "w-full "
                            "justify-end "
                            "gap-3 "
                            "mt-auto"
                        ):

                            ui.button(
                                "Cancel",
                                on_click=lambda:
                                ui.notify(
                                    "Valuation preview cancelled."
                                ),
                            ).props(
                                "outline "
                                "color=grey-7 "
                                "no-caps"
                            ).classes(
                                "px-5"
                            )

                            
                            ui.button(
                                f'Accept ${preview["estimate"]:,.2f}'
                                if preview["estimate"] is not None
                                else "No valuation available",

                                on_click=accept_valuation,
                            ).props(
                                "unelevated "
                                "color=primary "
                                "no-caps"
                            ).classes(
                                "px-5"
                            )

        valuation_preview()