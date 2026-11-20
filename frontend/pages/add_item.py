from datetime import date

import requests
from nicegui import app, ui

from backend_client import (
    BACKEND_URL,
    authenticated_session,
    csrf_headers,
)
from utilities.nav_wrapper import build_app_shell
from utilities.location_management import LocationControls, _sign_in_again
from utilities.uploads import read_upload

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
            "locations": data.get("locations"),
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
    
def upload_attachment(session, item_id, filename, content, content_type):
    """Upload one photo or receipt through the existing attachment endpoint."""
    file_type = (
        "receipt"
        if "pdf" in (content_type or "").lower() or "receipt" in filename.lower()
        else "photo"
    )
    response = session.post(
        f"{BACKEND_URL}/api/item/{item_id}/attachments/",
        data={"file_type": file_type},
        files={"file": (filename, content, content_type or "application/octet-stream")},
        headers=csrf_headers(session),
        timeout=30,
    )
    return response

# PAGE
# ============================================================
@ui.page("/add-item/{inventory_id}")
async def add_item_page(
    inventory_id: str,
):
    await ui.context.client.connected()
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

    # Each entry is (filename, bytes, content_type, file_type).
    uploaded_files = []

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

                    location_controls = LocationControls(
                        inventory_id, locations=options.get("locations"),
                    )
                    location_error = ui.label().classes("field-error").props("role=alert").mark("item-location-error")
                    location_error.visible = False

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
                    quantity_error = ui.label().classes("field-error")
                    quantity_error.visible = False

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
                                value=date.today().isoformat(),
                            )
                            .props(f'outlined type=date max="{date.today().isoformat()}"')
                            .classes("form-control w-full")
                        )       

                        purchase_amount_input = (
                            ui.number(
                                label=("Purchase Price ($) *"),
                                min=0,
                                step=0.01,
                                precision=2,
                                format="%.2f",
                                validation={
                                    "Purchase price cannot be negative.": lambda value: 
                                        value is None or value >= 0,
                                }
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                        manual_value_input = (
                            ui.number(
                                label=("Manual Value ($)"),
                                min=0,
                                step=0.01,
                                precision=2,
                                format="%.2f",
                            )
                            .props("outlined")
                            .classes("form-control w-full")
                        )

                    with ui.row().classes("w-full gap-6"):

                        date_error = ui.label().classes("field-error hidden")

                        amount_error = ui.label().classes("field-error hidden")

                    ui.label(
                        (
                            "Leave manual value blank to use an accepted "
                            "estimate, or the purchase price until you accept one."
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
                        "photo-placeholder w-full items-center justify-center gap-2 p-5"
                    ):
                        ui.icon("add_photo_alternate").classes("text-5xl text-slate-400")
                        ui.label("Upload photos or receipts").classes(
                            "font-semibold text-slate-700"
                        )
                        ui.label("PNG, JPG, or PDF. Select one photo as the cover.").classes(
                            "text-xs muted"
                        )

                    attachment_list = ui.column().classes("w-full gap-2")
                    cover_select = ui.select(
                        options={}, label="Cover photo", value=None
                    ).props("outlined dense").classes("w-full")

                    async def attachment_selected(e):
                        file_bytes, filename, content_type = await read_upload(e)
                        content_type = content_type or "application/octet-stream"
                        file_type = (
                            "receipt"
                            if "pdf" in content_type.lower() or "receipt" in filename.lower()
                            else "photo"
                        )
                        uploaded_files.append((filename, file_bytes, content_type, file_type))
                        index = len(uploaded_files) - 1
                        if file_type == "photo" and cover_select.value is None:
                            cover_select.value = str(index)
                        photo_options = {
                            str(i): entry[0]
                            for i, entry in enumerate(uploaded_files)
                            if entry[3] == "photo"
                        }
                        cover_select.options = photo_options
                        cover_select.update()
                        with attachment_list:
                            with ui.row().classes(
                                "w-full items-center justify-between rounded-lg bg-slate-50 border border-slate-200 px-3 py-2"
                            ):
                                ui.icon("receipt" if file_type == "receipt" else "image").classes(
                                    "text-blue-600"
                                )
                                ui.label(filename).classes("text-sm truncate")
                                ui.label("Receipt" if file_type == "receipt" else "Photo").classes(
                                    "text-xs muted"
                                )
                        ui.notify(f"'{filename}' added to the item.", type="positive")

                    ui.upload(
                        label="Choose Attachments",
                        on_upload=attachment_selected,
                        auto_upload=True,
                    ).props("multiple accept=image/*,.pdf flat bordered").classes("w-full")

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

                    required_indicators = {}
                    for required_key, required_text in [
                        ("name", "Item name"),
                        ("category", "Category"),
                        ("date", "Date acquired"),
                        ("price", "Purchase price"),
                    ]:
                        with ui.row().classes("items-center gap-2"):
                            indicator = ui.icon("radio_button_unchecked").classes(
                                "text-slate-400 text-lg"
                            )
                            ui.label(required_text).classes("text-sm text-slate-700")
                            required_indicators[required_key] = indicator

        def update_required_status(*_):
            """Keep the required-information checklist in sync with the form."""
            name_complete = bool((name_input.value or "").strip())
            category_complete = bool(category_select.value)
            try:
                acquired = date.fromisoformat(str(purchase_date_input.value or ""))
                date_complete = acquired <= date.today()
            except (TypeError, ValueError):
                date_complete = False
            try:
                price = float(purchase_amount_input.value)
                price_complete = price >= 0
            except (TypeError, ValueError):
                price_complete = False

            statuses = {
                "name": name_complete,
                "category": category_complete,
                "date": date_complete,
                "price": price_complete,
            }
            for key, complete in statuses.items():
                indicator = required_indicators[key]
                indicator.set_name("check_circle" if complete else "radio_button_unchecked")
                indicator.classes(
                    add="text-green-600" if complete else "text-slate-400",
                    remove="text-slate-400" if complete else "text-green-600",
                )

        name_input.on_value_change(update_required_status)
        category_select.on_value_change(update_required_status)
        purchase_date_input.on_value_change(update_required_status)
        purchase_amount_input.on_value_change(update_required_status)
        update_required_status()

        # SUBMIT
        # ====================================================
        # SUBMIT
        # ====================================================
        async def submit_form():

            error_label.classes(remove="hidden")
            error_label.visible = False
            success_label.visible = False

            for label in [
                name_error,
                category_error,
                date_error,
                amount_error,
                quantity_error,
                location_error,
            ]:
                label.classes(remove="hidden")
                label.visible = False
            quantity_input.props(remove="error")

            if not location_controls.ready:
                location_error.text = "Locations are unavailable. Retry loading locations before saving."
                location_error.visible = True
                return

            name = (name_input.value or "").strip()
            try:
                quantity = float(quantity_input.value)
                if quantity < 1 or not quantity.is_integer():
                    raise ValueError
            except (TypeError, ValueError):
                quantity_error.text = "Quantity must be a whole number of at least 1."
                quantity_error.visible = True
                quantity_input.props("error")
                error_label.text = "Please correct the highlighted fields."
                error_label.visible = True
                return

            form_data = {
                "name": name,
                "category": (category_select.value or ""),
                "location": location_controls.value,
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
                "quantity": int(quantity),
                "manual_value": (
                    manual_value_input.value
                    if (manual_value_input.value is not None)
                    else ""
                ),
                "notes": (notes_input.value or ""),
            }

            # Prepare files dictionary if a photo was attached
            try:
                session = authenticated_session()
                response = session.post(
                    f"{BACKEND_URL}/api/inventory/{inventory_id}/add-item/",
                    data=form_data,
                    headers=csrf_headers(session),
                    timeout=10,
                )
            except requests.RequestException:
                error_label.text = "Could not connect to the backend."
                error_label.visible = True
                return

            if response.status_code == 401:
                _sign_in_again()
                return

            try:
                result = response.json()
            except ValueError:
                result = {}

            if not (response.ok and result.get("success")):
                server_errors = result.get("errors", {})
                for field, label in {
                    "name": name_error,
                    "category": category_error,
                    "location": location_error,
                    "purchase_date": date_error,
                    "purchase_amount": amount_error,
                    "quantity": quantity_error,
                }.items():
                    if field in server_errors:
                        message = server_errors[field]
                        if isinstance(message, list):
                            message = message[0] if message else "Invalid value."
                        label.text = str(message)
                        label.visible = True
                error_label.text = result.get(
                    "error", "Couldn't add the item. Check the highlighted fields."
                )
                error_label.visible = True
                return

            item_id = result["item_id"]

            # Upload the selected cover photo first so it becomes the initial
            # photo if the backend automatically promotes the first photo.
            cover_index = cover_select.value
            ordered_files = list(enumerate(uploaded_files))
            if cover_index is not None:
                ordered_files.sort(key=lambda pair: pair[0] != int(cover_index))

            upload_failed = False
            cover_uploaded = False
            cover_attachment_id = None
            for original_index, (filename, content, content_type, file_type) in ordered_files:
                try:
                    upload_response = upload_attachment(
                        session, item_id, filename, content, content_type
                    )
                    if not upload_response.ok:
                        upload_failed = True
                        continue
                    if str(original_index) == str(cover_index):
                        cover_uploaded = True
                        try:
                            upload_data = upload_response.json()
                            attachment_data = upload_data.get("attachment", upload_data)
                            cover_attachment_id = (
                                attachment_data.get("public_id")
                                or attachment_data.get("id")
                            )
                        except (ValueError, AttributeError):
                            pass
                except requests.RequestException:
                    upload_failed = True

            # The upload response may not include the attachment ID. Resolve it
            # from the attachment list and explicitly set the selected cover.
            if cover_index is not None and cover_uploaded:
                if not cover_attachment_id:
                    try:
                        attachments_response = session.get(
                            f"{BACKEND_URL}/api/item/{item_id}/attachments/",
                            timeout=10,
                        )
                        attachments = attachments_response.json().get("attachments", [])
                        cover_filename = uploaded_files[int(cover_index)][0]
                        matching = [
                            att for att in attachments
                            if att.get("file_type") == "photo"
                            and att.get("original_filename") == cover_filename
                        ]
                        if matching:
                            cover_attachment_id = matching[-1].get("public_id")
                    except (requests.RequestException, ValueError, TypeError):
                        pass

                if cover_attachment_id:
                    try:
                        primary_response = session.post(
                            f"{BACKEND_URL}/api/attachment/{cover_attachment_id}/primary/",
                            headers=csrf_headers(session),
                            timeout=10,
                        )
                        if not primary_response.ok:
                            upload_failed = True
                    except requests.RequestException:
                        upload_failed = True
                else:
                    upload_failed = True

            if cover_index is not None and not cover_uploaded:
                upload_failed = True

            if upload_failed:
                ui.notify(
                    "Item was added, but one or more attachments could not be uploaded or the cover photo could not be set. You can finish in Edit Item.",
                    type="warning",
                )
                ui.navigate.to(f"/edit-item/{item_id}")
                return

            ui.notify("Item added successfully.", type="positive")
            ui.navigate.to("/inventory")

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