from datetime import date

import requests
from nicegui import app, ui

from backend_client import (
    BACKEND_URL,
    authenticated_session,
    csrf_headers,
)
from utilities.nav_wrapper import build_app_shell

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

    .add-item-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }

    .form-card {
        background: #ffffff;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .form-section-title {
        color: #0f172a;
        font-size: 18px;
        font-weight: 700;
    }

    .form-control .q-field__control {
        min-height: 48px;
    }

    .field-error {
        color: #dc2626;
        font-size: 12px;
        margin-top: -8px;
    }

    .photo-panel {
        background: #ffffff;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .photo-placeholder {
        width: 100%;
        min-height: 220px;
        background: #f8fafc;
        border: 2px dashed #cbd5e1;
        border-radius: 12px;

        display: flex;
        align-items: center;
        justify-content: center;
    }

    .add-item-tip {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
    }

    .required-note {
        color: #64748b;
        font-size: 12px;
    }

    .form-actions {
        border-top: 1px solid #e2e8f0;
        padding-top: 20px;
    }

    @media (max-width: 1050px) {
        .add-item-layout {
            grid-template-columns: 1fr !important;
        }
    }
""",
    shared=True,
)


# BACKEND DATA
# ============================================================
def load_add_item_options(
    inventory_id: str,
) -> dict:

    if not inventory_id or inventory_id == "None":
        return {
            "inventory_name": "Inventory",
            "categories": {},
        }

    try:
        response = authenticated_session().get(
            (f"{BACKEND_URL}/api/inventory/" f"{inventory_id}/add-item/"),
            timeout=5,
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            return {
                "inventory_name": "Inventory",
                "categories": {},
            }

        category_options = {}

        for category in data.get(
            "categories",
            [],
        ):

            category_id = str(category.get("id") or category.get("pk"))

            category_name = category.get("name")

            if category_id and category_name:
                category_options[category_id] = category_name

        return {
            "inventory_name": (
                data.get(
                    "inventory",
                    {},
                ).get(
                    "name",
                    "Inventory",
                )
            ),
            "categories": (category_options),
        }

    except requests.RequestException as error:

        print(
            "Error loading Add Item options:",
            error,
        )

        return {
            "inventory_name": "Inventory",
            "categories": {},
        }


# PAGE
# ============================================================
@ui.page("/add-item/{inventory_id}")
def add_item_page(
    inventory_id: str,
):

    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title("Add Item | CoverWorth")

    build_app_shell(
        "Inventory",
        username=app.storage.user.get(
            "username",
            "User",
        ),
    )

    options = load_add_item_options(inventory_id)

    categories = options["categories"]

    inventory_name = options["inventory_name"]

    # MAIN CONTENT
    # ========================================================
    with ui.column().classes("add-item-container " "page-content-frame " "p-7 gap-5"):

        # PAGE HEADER
        # ====================================================
        with ui.row().classes("w-full " "items-center " "justify-between " "gap-4"):

            with ui.column().classes("gap-1"):

                ui.button(
                    "Back to Inventory",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props("flat " "color=primary " "no-caps").classes("self-start -ml-3")

                ui.label("Add Item").classes("text-4xl " "font-bold " "tracking-tight")

                ui.label(("Add a new belonging to " f"{inventory_name}")).classes(
                    "text-base muted"
                )

        # MESSAGE AREA
        # ====================================================
        success_label = ui.label().classes(
            "w-full "
            "bg-green-50 "
            "text-green-700 "
            "border "
            "border-green-200 "
            "rounded-lg "
            "px-4 py-3 "
            "font-medium hidden"
        )

        error_label = ui.label().classes(
            "w-full "
            "bg-red-50 "
            "text-red-700 "
            "border "
            "border-red-200 "
            "rounded-lg "
            "px-4 py-3 "
            "font-medium hidden"
        )

        # TWO-COLUMN LAYOUT
        # ====================================================
        with ui.grid().classes(
            "add-item-layout "
            "w-full "
            "grid-cols-[minmax(0,1.7fr)_minmax(300px,0.8fr)] "
            "gap-5"
        ):

            # LEFT COLUMN
            # =================================================
            with ui.column().classes("w-full gap-5"):

                # BASIC INFORMATION
                # =============================================
                with ui.card().classes("form-card " "w-full p-6 gap-5"):

                    with ui.column().classes("gap-0"):

                        ui.label("Basic Information").classes("form-section-title")

                        ui.label(
                            ("Start with the details " "that identify this item.")
                        ).classes("text-sm muted")

                    name_input = (
                        ui.input(
                            label="Item Name *",
                        )
                        .props("outlined")
                        .classes("form-control w-full")
                    )

                    name_error = ui.label().classes("field-error hidden")

                    # Category row
                    with ui.row().classes("w-full " "items-end " "gap-3 " "flex-wrap"):

                        category_select = (
                            ui.select(
                                options=categories,
                                label="Category *",
                            )
                            .props("outlined")
                            .classes("form-control " "min-w-[240px] " "flex-1")
                        )

                        ui.button(
                            "Manage Categories",
                            icon="category",
                            on_click=lambda: ui.navigate.to("/categories"),
                        ).props("outline " "color=primary " "no-caps").classes(
                            "h-[48px]"
                        )

                    category_error = ui.label().classes("field-error hidden")

                    description_input = (
                        ui.textarea(
                            label="Description"
                        )
                        .props("outlined rows=3")
                        .classes("w-full")
                    )

                # ITEM DETAILS
                # =============================================
                with ui.card().classes("form-card " "w-full p-6 gap-5"):

                    with ui.column().classes("gap-0"):

                        ui.label("Item Details").classes("form-section-title")

                        ui.label(
                            (
                                "Record identifying "
                                "information for future "
                                "reference."
                            )
                        ).classes("text-sm muted")

                    with ui.grid(columns=2).classes(
                        "w-full gap-4 " "max-sm:grid-cols-1"
                    ):

                        brand_input = (
                            ui.input(
                                label="Brand"
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                        model_input = (
                            ui.input(
                                label="Model Number"
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                        serial_input = (
                            ui.input(
                                label="Serial Number"
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                        condition_select = (
                            ui.select(
                                options={
                                    "new": "New",
                                    "like_new": ("Like New"),
                                    "used": "Used",
                                    "damaged": ("Damaged"),
                                    "unknown": ("Unknown"),
                                },
                                value="unknown",
                                label="Condition",
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                    quantity_input = (
                        ui.number(
                            label="Quantity",
                            value=1,
                            min=1,
                            step=1,
                        )
                        .props("outlined")
                        .classes("form-control " "w-full " "max-w-[220px]")
                    )

                # PURCHASE AND VALUE
                # =============================================
                with ui.card().classes("form-card " "w-full p-6 gap-5"):

                    with ui.column().classes("gap-0"):

                        ui.label("Purchase & Value").classes("form-section-title")

                        ui.label(
                            (
                                "Record when the item "
                                "was acquired and what "
                                "you paid for it."
                            )
                        ).classes("text-sm muted")

                    with ui.grid(columns=2).classes(
                        "w-full gap-4 " "max-sm:grid-cols-1"
                    ):

                        purchase_date_input = (
                            ui.input(
                                label="Date Acquired *",
                                value=(date.today().isoformat()),
                            )
                            .props("outlined type=date")
                            .classes("form-control w-full")
                        )

                        purchase_amount_input = (
                            ui.number(
                                label=("Purchase Price ($) *"),
                                min=0,
                                step=0.01,
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                        manual_value_input = (
                            ui.number(
                                label=("Manual Value ($)"),
                                min=0,
                                step=0.01,
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                    with ui.row().classes("w-full gap-6"):

                        date_error = ui.label().classes("field-error hidden")

                        amount_error = ui.label().classes("field-error hidden")

                    ui.label(
                        (
                            "If no manual value is "
                            "entered, CoverWorth currently "
                            "uses the purchase price as "
                            "the initial manual value."
                        )
                    ).classes("required-note")

                # NOTES
                # =============================================
                with ui.card().classes("form-card " "w-full p-6 gap-4"):

                    with ui.column().classes("gap-0"):

                        ui.label("Notes").classes("form-section-title")

                        ui.label(
                            ("Anything else you want " "to remember about this item.")
                        ).classes("text-sm muted")

                    notes_input = (
                        ui.textarea(
                            label="Notes",
                            placeholder=(
                                "Warranty details, provenance, special instructions, etc."
                            ),
                        )
                        .props("outlined rows=4")
                        .classes("w-full")
                    )

            # RIGHT COLUMN
            # =================================================
            with ui.column().classes("w-full gap-5"):

                # PHOTO
                # =============================================
                with ui.card().classes("photo-panel " "w-full p-5 gap-4"):

                    ui.label("Item Photo").classes("form-section-title")

                    ui.label(
                        ("Add a clear photo to make " "the item easier to identify.")
                    ).classes("text-sm muted")

                    with ui.column().classes(
                        "photo-placeholder "
                        "w-full "
                        "items-center "
                        "justify-center "
                        "gap-2 p-5"
                    ):

                        ui.icon("add_photo_alternate").classes(
                            "text-5xl " "text-slate-400"
                        )

                        ui.label("Upload a photo").classes(
                            "font-semibold " "text-slate-700"
                        )

                        ui.label(("PNG or JPG image")).classes("text-xs muted")

                    def photo_selected(event):

                        ui.notify(
                            (
                                f"{event.name} selected. "
                                "Photo persistence will "
                                "be connected when the "
                                "attachment API story "
                                "is implemented."
                            ),
                            type="info",
                        )

                    ui.upload(
                        label="Choose Photo",
                        on_upload=(photo_selected),
                        auto_upload=True,
                        max_files=1,
                    ).props("accept=image/*").classes("w-full")

                # TIPS
                # =============================================
                with ui.row().classes(
                    "add-item-tip " "w-full " "items-start " "gap-3 p-4 " "flex-nowrap"
                ):

                    ui.icon("lightbulb").classes("text-2xl " "text-blue-600")

                    with ui.column().classes("gap-1"):

                        ui.label("Good inventory records").classes(
                            "font-semibold " "text-blue-900"
                        )

                        ui.label(
                            (
                                "Include brand, model, "
                                "serial number, purchase "
                                "price, and a clear photo "
                                "when those details are "
                                "available."
                            )
                        ).classes("text-sm " "text-blue-800")

                # REQUIRED FIELD NOTE
                # =============================================
                with ui.card().classes("form-card " "w-full p-5 gap-2"):

                    ui.label("Required Information").classes("font-semibold")

                    for text in [
                        "Item name",
                        "Category",
                        "Date acquired",
                        "Purchase price",
                    ]:

                        with ui.row().classes("items-center gap-2"):

                            ui.icon("check_circle").classes("text-green-600 " "text-lg")

                            ui.label(text).classes("text-sm " "text-slate-700")

        # SUBMIT
        # ====================================================
        async def submit_form():

            error_label.visible = False
            success_label.visible = False

            for label in [
                name_error,
                category_error,
                date_error,
                amount_error,
            ]:
                label.visible = False

            name = (name_input.value or "").strip()

            form_data = {
                "name": name,
                "category": (category_select.value or ""),
                "purchase_date": (purchase_date_input.value or ""),
                "purchase_amount": (
                    purchase_amount_input.value
                    if (purchase_amount_input.value is not None)
                    else ""
                ),
                "description": (description_input.value or ""),
                "brand": (brand_input.value or ""),
                "model_number": (model_input.value or ""),
                "serial_number": (serial_input.value or ""),
                "condition": (condition_select.value),
                "quantity": (quantity_input.value or 1),
                "manual_value": (
                    manual_value_input.value
                    if (manual_value_input.value is not None)
                    else ""
                ),
                "notes": (notes_input.value or ""),
            }

            try:

                session = authenticated_session()

                response = session.post(
                    (
                        f"{BACKEND_URL}"
                        f"/api/inventory/"
                        f"{inventory_id}"
                        "/add-item/"
                    ),
                    data=form_data,
                    headers=csrf_headers(session),
                    timeout=10,
                )

                data = response.json()

                if response.ok:

                    success_label.text = data.get(
                        "message",
                        ("Item added " "successfully."),
                    )

                    success_label.visible = True

                    ui.notify(
                        "Item added successfully.",
                        type="positive",
                    )

                    ui.timer(
                        1.0,
                        lambda: ui.navigate.to("/inventory"),
                        once=True,
                    )

                    return

                errors = data.get(
                    "errors",
                    {},
                )

                field_labels = {
                    "name": name_error,
                    "category": (category_error),
                    "purchase_date": (date_error),
                    "purchase_amount": (amount_error),
                }

                for (
                    field,
                    label,
                ) in field_labels.items():

                    if field in errors:

                        message = errors[field]

                        if isinstance(
                            message,
                            list,
                        ):
                            message = message[0] if message else ""

                        label.text = str(message)

                        label.visible = True

                error_label.text = data.get(
                    "error",
                    ("Please correct " "the highlighted fields."),
                )

                error_label.visible = True

            except requests.RequestException:

                error_label.text = "Could not connect " "to the backend."

                error_label.visible = True

        with ui.row().classes(
            "form-actions " "w-full " "items-center " "justify-between " "gap-4"
        ):

            ui.label("* Required field").classes("required-note")

            with ui.row().classes("items-center gap-3"):

                ui.button(
                    "Cancel",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props("outline " "color=grey-7 " "no-caps").classes("px-5")

                ui.button(
                    "Add Item",
                    icon="add",
                    on_click=submit_form,
                ).props(
                    "unelevated " "color=primary " "no-caps"
                ).classes("px-6 py-2 " "rounded-lg")
