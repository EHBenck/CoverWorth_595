from datetime import datetime
import requests
from nicegui import app, run, ui
from backend_client import (
    BACKEND_URL,
    authenticated_session,
)
from utilities.nav_wrapper import build_app_shell
from utilities.attachments import attachment_url

# ITEM DETAILS PAGE
# ============================================================

# STYLING
# ============================================================

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

    .item-detail-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }


    /* ========================================================
       CARDS
       ======================================================== */

    .detail-card {
        width: 100%;

        background: #ffffff;

        border: 1px solid #e1e7ef;
        border-radius: 12px;

        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .detail-section-title {
        color: #0f172a;

        font-size: 18px;
        font-weight: 700;
    }


    /* ========================================================
       ITEM IMAGE
       ======================================================== */

    .item-photo {
        width: 100%;
        min-height: 260px;
        overflow: hidden;

        background: #f8fafc;

        border: 1px solid #e2e8f0;
        border-radius: 12px;

        display: flex;
        align-items: center;
        justify-content: center;
    }


    /* ========================================================
       DETAIL FIELDS
       ======================================================== */

    .detail-field {
        min-height: 64px;

        padding: 12px 0;

        border-bottom: 1px solid #edf2f7;
    }

    .detail-field:last-child {
        border-bottom: none;
    }

    .detail-label {
        color: #64748b;

        font-size: 12px;
        font-weight: 600;

        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .detail-value {
        color: #0f172a;

        font-size: 15px;
        font-weight: 500;
    }


    /* ========================================================
       VALUE CARD
       ======================================================== */

    .value-card {
        background: #f8fbff;

        border: 1px solid #dbeafe;
        border-radius: 12px;
    }

    .value-number {
        color: #0f172a;

        font-size: 34px;
        font-weight: 700;

        line-height: 1.1;
    }

    .value-source {
        color: #64748b;
        font-size: 13px;
    }


    /* ========================================================
       CATEGORY BADGE
       ======================================================== */

    .category-badge {
        display: inline-block;

        width: fit-content;

        padding: 5px 12px;

        border-radius: 999px;

        background: #eff6ff;
        color: #1d4ed8;

        font-size: 12px;
        font-weight: 600;
    }


    /* ========================================================
       NOTES
       ======================================================== */

    .notes-box {
        min-height: 90px;

        background: #f8fafc;

        border: 1px solid #e2e8f0;
        border-radius: 8px;

        padding: 14px;
    }


    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 1050px) {

        .item-detail-layout {
            grid-template-columns: 1fr !important;
        }
    }
    """,
    shared=True,
)


# HELPERS
# ============================================================


def fetch_item_detail(
    item_id: str,
    cookies: dict,
) -> dict | None:

    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/item/{item_id}/",
            timeout=10,
        )

        if response.status_code == 401:
            return None

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            return {}

        return data

    except (
        requests.RequestException,
        ValueError,
    ) as error:

        print(f"[ITEM DETAIL] Failed to load item: {error}")

        return {}


def fetch_item_photo(
    item_id: str,
    cookies: dict,
) -> str | None:
    """Return the URL of the item's first saved photo attachment, if any."""

    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/item/{item_id}/attachments/",
            timeout=10,
        )

        if not response.ok:
            return None

        for attachment in response.json().get("attachments", []):
            if attachment.get("file_type") == "photo":
                url = attachment_url(attachment.get("file_url") or "")
                if url:
                    return url

    except (requests.RequestException, ValueError) as error:
        print(f"[ITEM DETAIL] Failed to load photo: {error}")

    return None


def format_money(
    value,
) -> str:

    if value in (
        None,
        "",
    ):
        return "—"

    try:
        return f"${float(value):,.2f}"

    except (
        TypeError,
        ValueError,
    ):
        return "—"


def format_date(
    value,
    include_time: bool = False,
) -> str:

    if not value:
        return "—"

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

        if include_time:
            return parsed.strftime("%b %d, %Y at %I:%M %p").replace(
                " 0",
                " ",
            )

        return parsed.strftime("%b %d, %Y").replace(
            " 0",
            " ",
        )

    except (
        ValueError,
        TypeError,
    ):
        return str(value)


def detail_field(
    label: str,
    value,
) -> None:

    with ui.column().classes("detail-field w-full gap-1"):

        ui.label(label).classes("detail-label")

        ui.label(
            (
                str(value)
                if value
                not in (
                    None,
                    "",
                )
                else "—"
            )
        ).classes("detail-value")


# PAGE
# ============================================================
@ui.page("/item/{item_id}")
async def item_detail_page(
    item_id: str,
):

    # Authentication
    # --------------------------------------------------------
    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title("Item Details | CoverWorth")

    build_app_shell(
        "Inventory",
        username=app.storage.user.get(
            "username",
            "User",
        ),
    )

    # Loading state
    # --------------------------------------------------------
    with ui.column().classes(
        "item-detail-container "
        "page-content-frame "
        "items-center "
        "justify-center "
        "gap-3 p-8"
    ) as loading:

        ui.spinner(size="lg")

        ui.label("Loading item...").classes("muted")

    await ui.context.client.connected()

    cookies = dict(
        app.storage.user.get(
            "auth_cookies",
            {},
        )
    )

    data = await run.io_bound(
        fetch_item_detail,
        item_id,
        cookies,
    )

    loading.delete()

    # Session expired
    # --------------------------------------------------------
    if data is None:

        app.storage.user.pop(
            "auth_cookies",
            None,
        )

        app.storage.user.pop(
            "username",
            None,
        )

        ui.navigate.to("/")

        return

    # Item missing
    # --------------------------------------------------------
    if not data:

        with ui.column().classes(
            "item-detail-container "
            "page-content-frame "
            "items-center "
            "justify-center "
            "gap-4 p-10"
        ):

            ui.icon("inventory_2").classes("text-6xl " "text-slate-300")

            ui.label("Item not found").classes("text-2xl font-bold")

            ui.label(
                ("The item may have been removed " "or you may not have access to it.")
            ).classes("muted")

            ui.button(
                "Back to Inventory",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to("/inventory"),
            ).props("unelevated " "color=primary " "no-caps")

        return

    item = data.get(
        "item",
        {},
    )

    inventory = data.get(
        "inventory",
        {},
    )

    photo_url = attachment_url(item.get("primary_photo_url") or "") or (
        await run.io_bound(fetch_item_photo, item_id, cookies)
    )

    effective_value = item.get("effective_value")

    manual_value = item.get("manual_value")

    value_source = {
        "manual": "Manual value",
        "estimated": "Accepted estimate",
        "purchase": "Purchase price",
    }.get(item.get("effective_value_source"), "No current valuation")

    # MAIN CONTENT
    # ========================================================
    with ui.column().classes(
        "item-detail-container " "page-content-frame " "p-7 gap-5"
    ):

        # HEADER
        # ====================================================
        with ui.row().classes("w-full " "items-start " "justify-between " "gap-4"):

            with ui.column().classes("gap-1"):

                ui.button(
                    "Back to Inventory",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props("flat " "color=primary " "no-caps").classes("self-start -ml-3")

                ui.label(
                    item.get(
                        "name",
                        "Item",
                    )
                ).classes("text-4xl " "font-bold " "tracking-tight")

                with ui.row().classes("items-center gap-3"):

                    ui.label(
                        item.get(
                            "category",
                            "Uncategorized",
                        )
                    ).classes("category-badge")

                    ui.label(
                        inventory.get(
                            "name",
                            "Inventory",
                        )
                    ).classes("text-sm muted")

            ui.button(
                "Edit Item",
                icon="edit",
                on_click=lambda: ui.navigate.to(f"/edit-item/{item_id}"),
            ).props("unelevated " "color=primary " "no-caps").classes(
                "px-5 py-2 " "rounded-lg"
            )

        # TWO-COLUMN LAYOUT
        # ====================================================
        with ui.grid().classes(
            "item-detail-layout "
            "w-full "
            "grid-cols-[minmax(0,1.65fr)_minmax(300px,0.8fr)] "
            "gap-5"
        ):

            # LEFT COLUMN
            # =================================================
            with ui.column().classes("w-full gap-5"):

                # DESCRIPTION
                # =============================================
                with ui.card().classes("detail-card " "w-full p-6 gap-4"):

                    ui.label("About This Item").classes("detail-section-title")

                    description = (
                        item.get("description") or "No description has been added."
                    )

                    ui.label(description).classes(
                        "text-sm " "text-slate-700 " "leading-relaxed"
                    )

                # ITEM INFORMATION
                # =============================================
                with ui.card().classes("detail-card " "w-full p-6 gap-4"):

                    ui.label("Item Information").classes("detail-section-title")

                    with ui.grid(columns=2).classes(
                        "w-full " "gap-x-8 " "max-sm:grid-cols-1"
                    ):

                        detail_field(
                            "Category",
                            item.get("category"),
                        )

                        detail_field(
                            "Location",
                            item.get("location") or "Unassigned",
                        )

                        detail_field(
                            "Brand",
                            item.get("brand"),
                        )

                        detail_field(
                            "Model Number",
                            item.get("model_number"),
                        )

                        detail_field(
                            "Serial Number",
                            item.get("serial_number"),
                        )

                        detail_field(
                            "Condition",
                            item.get("condition"),
                        )

                        detail_field(
                            "Quantity",
                            item.get("quantity"),
                        )

                # PURCHASE INFORMATION
                # =============================================
                with ui.card().classes("detail-card " "w-full p-6 gap-4"):

                    ui.label("Purchase & Value").classes("detail-section-title")

                    with ui.grid(columns=3).classes(
                        "w-full " "gap-x-8 " "max-md:grid-cols-1"
                    ):

                        detail_field(
                            "Date Acquired",
                            format_date(item.get("purchase_date")),
                        )

                        detail_field(
                            "Purchase Price",
                            format_money(item.get("purchase_amount")),
                        )

                        detail_field(
                            "Manual Value",
                            format_money(manual_value),
                        )

                # NOTES
                # =============================================
                with ui.card().classes("detail-card " "w-full p-6 gap-4"):

                    ui.label("Notes").classes("detail-section-title")

                    with ui.element("div").classes("notes-box"):

                        ui.label(
                            (item.get("notes") or "No notes have been added.")
                        ).classes("text-sm " "text-slate-700 " "leading-relaxed")

            # RIGHT COLUMN
            # =================================================
            with ui.column().classes("w-full gap-5"):

                # PHOTO
                # =============================================
                with ui.card().classes("detail-card " "w-full p-5 gap-4"):

                    ui.label("Item Photo").classes("detail-section-title")

                    with ui.element("div").classes("item-photo"):

                        if photo_url:
                            ui.image(photo_url).classes("w-full object-contain")
                        else:
                            ui.icon("inventory_2").classes("text-7xl " "text-slate-300")

                    if not photo_url:
                        ui.label(
                            "No photo yet. Add one from the Edit Item page."
                        ).classes("text-xs muted")

                # CURRENT VALUE
                # =============================================
                with ui.card().classes("value-card " "w-full p-6 gap-3"):

                    ui.label("Current Value").classes(
                        "text-sm " "font-semibold " "text-slate-600"
                    )

                    ui.label(
                        (
                            format_money(effective_value)
                            if effective_value is not None
                            else "Not valued"
                        )
                    ).classes("value-number").mark("current-item-value")

                    ui.label(value_source).classes("value-source").mark("current-value-source")

                    if item.get("valuation_date"):

                        ui.label(
                            ("Last valued " f'{format_date(item["valuation_date"])}')
                        ).classes("text-xs muted")

                    ui.separator()

                    ui.button(
                        "View Valuations",
                        icon="analytics",
                        on_click=lambda: ui.navigate.to("/valuations"),
                    ).props("outline " "color=primary " "no-caps").classes("w-full")

                # RECORD DETAILS
                # =============================================
                with ui.card().classes("detail-card " "w-full p-6 gap-3"):

                    ui.label("Record Details").classes("detail-section-title")

                    detail_field(
                        "Inventory",
                        inventory.get("name"),
                    )

                    detail_field(
                        "Created",
                        format_date(item.get("created_at")),
                    )

                    detail_field(
                        "Last Updated",
                        format_date(item.get("updated_at")),
                    )