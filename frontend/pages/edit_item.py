
from datetime import date, datetime
from unicodedata import name

import requests
from nicegui import app, ui

from backend_client import BACKEND_URL, authenticated_session, csrf_headers
from utilities.nav_wrapper import build_app_shell
from utilities.attachments import attachment_url


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

    .edit-item-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }

    .form-card, .photo-panel {
        background: #ffffff;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
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

    .edit-item-tip {
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
        .edit-item-layout {
            grid-template-columns: 1fr !important;
        }
    }
    """,
    shared=True,
)


async def load_item_data(item_id: str) -> dict:
    """Fetch the item and available categories."""
    try:
        response = authenticated_session().get(
            f"{BACKEND_URL}/api/item/{item_id}/edit/",
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("success"):
            return {
                "item": data.get("item", {}),
                "categories": data.get("categories", []),
            }

        return {"item": {}, "categories": []}

    except requests.RequestException as error:
        print(f"Error loading item: {error}")
        return {"item": {}, "categories": []}


@ui.page("/edit-item/{item_id}")
async def edit_item_page(item_id: str):
    await ui.context.client.connected()

    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title("Edit Item | CoverWorth")

    build_app_shell(
        "Inventory",
        username=app.storage.user.get("username", "User"),
    )

    data = await load_item_data(item_id)
    item = data.get("item", {})
    categories = data.get("categories", [])

    if not item:
        with ui.column().classes(
            "w-full items-center justify-center p-10"
        ):
            ui.label("Item not found").classes(
                "text-xl font-bold text-red-600"
            )
            ui.button(
                "Back to Inventory",
                on_click=lambda: ui.navigate.to("/inventory"),
            )
        return

    category_options = {
        str(category.get("id", category.get("pk"))): category["name"]
        for category in categories
        if category.get("name") and (
            category.get("id") is not None
            or category.get("pk") is not None
        )
    }

    existing_category = item.get("category_id")
    if existing_category is None and isinstance(item.get("category"), dict):
        existing_category = item["category"].get("id")

    existing_category = (
        str(existing_category) if existing_category is not None else None
    )

    # Parse the saved acquisition date.
    raw_date = item.get("purchase_date")
    try:
        if raw_date:
            initial_date = date.fromisoformat(str(raw_date)[:10])
        else:
            initial_date = date.today()
    except (ValueError, TypeError):
        initial_date = date.today()

    today = date.today()

    # Main content
    with ui.column().classes(
        "edit-item-container page-content-frame p-7 gap-5"
    ):
        # Header
        with ui.row().classes(
            "w-full items-center justify-between gap-4"
        ):
            with ui.column().classes("gap-1"):
                ui.button(
                    "Back to Inventory",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props(
                    "flat color=primary no-caps"
                ).classes("self-start -ml-3")

                ui.label("Edit Item").classes(
                    "text-4xl font-bold tracking-tight"
                )
                ui.label(
                    f"Update the details for {item.get('name', 'this item')}."
                ).classes("text-base muted")

        success_label = ui.label().classes(
            "w-full bg-green-50 text-green-700 border "
            "border-green-200 rounded-lg px-4 py-3 "
            "font-medium hidden"
        )

        error_label = ui.label().classes(
            "w-full bg-red-50 text-red-700 border "
            "border-red-200 rounded-lg px-4 py-3 "
            "font-medium hidden"
        )

        # Two-column layout
        with ui.grid().classes(
            "edit-item-layout w-full "
            "grid-cols-[minmax(0,1.7fr)_minmax(300px,0.8fr)] gap-5"
        ):
            # Left column
            with ui.column().classes("w-full gap-5"):
                # Basic Information
                with ui.card().classes("form-card w-full p-6 gap-5"):
                    with ui.column().classes("gap-0"):
                        ui.label("Basic Information").classes(
                            "form-section-title"
                        )
                        ui.label(
                            "Update the details that identify this item."
                        ).classes("text-sm muted")

                    name_input = ui.input(
                        label="Item Name *",
                        value=item.get("name", ""),
                    ).props("outlined").classes("form-control w-full")

                    name_error = ui.label().classes("field-error hidden")

                    category_select = ui.select(
                        options=category_options,
                        value=existing_category,
                        label="Category *",
                    ).props("outlined").classes(
                        "form-control w-full"
                    )

                    category_error = ui.label().classes("field-error hidden")

                    description_input = ui.textarea(
                        label="Description",
                        value=item.get("description") or "",
                    ).props("outlined rows=3").classes("w-full")

                # Item Details
                with ui.card().classes("form-card w-full p-6 gap-5"):
                    with ui.column().classes("gap-0"):
                        ui.label("Item Details").classes(
                            "form-section-title"
                        )
                        ui.label(
                            "Record identifying information for reference."
                        ).classes("text-sm muted")

                    with ui.grid(columns=2).classes(
                        "w-full gap-4 max-sm:grid-cols-1"
                    ):
                        brand_input = ui.input(
                            label="Brand",
                            value=item.get("brand") or "",
                        ).props("outlined").classes("form-control w-full")

                        model_input = ui.input(
                            label="Model Number",
                            value=item.get("model_number") or "",
                        ).props("outlined").classes("form-control w-full")

                        serial_input = ui.input(
                            label="Serial Number",
                            value=item.get("serial_number") or "",
                        ).props("outlined").classes("form-control w-full")

                        condition_select = ui.select(
                            options={
                                "new": "New",
                                "like_new": "Like New",
                                "used": "Used",
                                "damaged": "Damaged",
                                "unknown": "Unknown",
                            },
                            value=item.get("condition") or "unknown",
                            label="Condition",
                        ).props("outlined").classes("form-control w-full")

                    quantity_input = ui.number(
                        label="Quantity",
                        value=item.get("quantity") if item.get("quantity") is not None else 1,
                        min=1,
                        step=1,
                    ).props("outlined min=1").classes(
                        "form-control w-full max-w-[220px]"
                    )
                    quantity_error = ui.label().classes("field-error")
                    quantity_error.visible = False

                # Purchase and Value
                with ui.card().classes("form-card w-full p-6 gap-5"):
                    with ui.column().classes("gap-0"):
                        ui.label("Purchase & Value").classes(
                            "form-section-title"
                        )
                        ui.label(
                            "Update when the item was acquired and its value."
                        ).classes("text-sm muted")

                    with ui.grid(columns=2).classes(
                        "w-full gap-4 max-sm:grid-cols-1"
                    ):
                        purchase_date_input = ui.input(
                            label="Date Acquired *",
                            value=initial_date.isoformat(),
                        ).props(
                            f"outlined type=date max={today.isoformat()}"
                        ).classes("form-control w-full")

                        purchase_amount_input = ui.number(
                            label="Purchase Price ($) *",
                            value=(
                                float(item["purchase_amount"])
                                if item.get("purchase_amount") not in (None, "")
                                else None
                            ),
                            min=0,
                            step=0.01,
                        ).props("outlined min=0").classes(
                            "form-control w-full"
                        )

                        manual_value_input = ui.number(
                            label="Manual Value ($)",
                            value=(
                                float(item["manual_value"])
                                if item.get("manual_value") not in (None, "")
                                else None
                            ),
                            min=0,
                            step=0.01,
                        ).props("outlined min=0").classes(
                            "form-control w-full"
                        )

                    with ui.row().classes("w-full gap-6"):
                        date_error = ui.label().classes("field-error hidden")
                        amount_error = ui.label().classes("field-error hidden")

                    ui.label(
                        "Update the manual value only if you want to override "
                        "the item's estimated or initial value."
                    ).classes("required-note")

                # Notes
                with ui.card().classes("form-card w-full p-6 gap-4"):
                    with ui.column().classes("gap-0"):
                        ui.label("Notes").classes("form-section-title")
                        ui.label(
                            "Anything else you want to remember about this item."
                        ).classes("text-sm muted")

                    notes_input = ui.textarea(
                        label="Notes",
                        value=item.get("notes") or "",
                        placeholder=(
                            "Warranty details, provenance, special instructions, etc."
                        ),
                    ).props("outlined rows=4").classes("w-full")

            # Right column
            # Right column
            with ui.column().classes("w-full gap-5"):
                with ui.card().classes("photo-panel w-full p-5 gap-4"):
                    ui.label("Item Photos & Receipts").classes("form-section-title")
                    ui.label(
                        "Upload photos or receipts to attach to this item."
                    ).classes("text-sm muted")

                    attachments_container = ui.column().classes("w-full gap-3")

                    async def refresh_attachments():
                        attachments_container.clear()
                        try:
                            res = authenticated_session().get(
                                f"{BACKEND_URL}/api/item/{item_id}/attachments/",
                                timeout=5,
                            )
                            att_list = res.json().get("attachments", []) if res.ok else []
                        except requests.RequestException:
                            att_list = []

                        if not att_list:
                            with attachments_container:
                                with ui.column().classes(
                                    "photo-placeholder w-full items-center justify-center gap-2 p-5"
                                ):
                                    ui.icon("folder_open").classes("text-4xl text-slate-400")
                                    ui.label("No attachments yet").classes("font-semibold text-slate-700 text-sm")
                            return

                        with attachments_container:
                            for att in att_list:
                                with ui.row().classes(
                                    "w-full items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-lg"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        icon_name = "receipt" if att["file_type"] == "receipt" else "image"
                                        ui.icon(icon_name).classes("text-xl text-blue-600")
                                        ui.label(att["original_filename"] or "Attachment").classes("text-sm font-medium truncate max-w-[160px]")
                                    
                                    with ui.row().classes("items-center gap-1"):
                                        file_url = attachment_url(att.get("file_url") or "")
                                        if file_url:
                                            ui.button(icon="visibility", on_click=lambda url=file_url: ui.navigate.to(url, new_tab=True)).props("flat round dense size=sm")
                                        
                                        async def delete_att(aid=att["public_id"]):
                                            try:
                                                session = authenticated_session()
                                                response = session.delete(
                                                    f"{BACKEND_URL}/api/attachment/{aid}/",
                                                    headers=csrf_headers(session),
                                                    timeout=10,
                                                )
                                                if response.ok:
                                                    ui.notify("Attachment deleted.", type="positive")
                                                    await refresh_attachments()
                                                else:
                                                    ui.notify("Failed to delete attachment.", type="negative")
                                            except requests.RequestException:
                                                ui.notify("Connection error.", type="negative")

                                        ui.button(icon="delete", on_click=delete_att).props("flat round dense color=red size=sm")

                    # File Uploader
                    ui.upload(
                        label="Upload Photo / Receipt",
                        auto_upload=True,
                        on_upload=lambda e: handle_file_upload(e),
                    ).classes("w-full").props("accept=.jpg,.png,.jpeg,.pdf flat bordered")

                    async def handle_file_upload(e):
                        try:
                            session = authenticated_session()
                            file_bytes = await e.file.read()
                            name = e.file.name
                            content_type = e.file.content_type or "application/octet-stream"
                            files = {"file": (name, file_bytes, content_type)}
                            data = {
                                "file_type": "receipt"
                                if "pdf" in content_type or "receipt" in name.lower()
                                else "photo"
                            }
                            # ...the rest (session.post, notify, refresh_attachments) stays the same
                            
                            response = session.post(
                                f"{BACKEND_URL}/api/item/{item_id}/attachments/",
                                files=files,
                                data=data,
                                headers=csrf_headers(session),
                                timeout=15,
                            )
                            if response.ok:
                                ui.notify("File uploaded successfully!", type="positive")
                                await refresh_attachments()
                            else:
                                ui.notify("Upload failed.", type="negative")
                        except requests.RequestException as err:
                            ui.notify(f"Error uploading: {err}", type="negative")

                    # Initial load
                    ui.timer(0.1, refresh_attachments, once=True)

                with ui.row().classes(
                    "edit-item-tip w-full items-start gap-3 p-4 flex-nowrap"
                ):
                    ui.icon("lightbulb").classes("text-2xl text-blue-600")

                    with ui.column().classes("gap-1"):
                        ui.label("Keep records up to date").classes(
                            "font-semibold text-blue-900"
                        )
                        ui.label(
                            "Review identifying details, purchase information, "
                            "and valuation when updating your inventory."
                        ).classes("text-sm text-blue-800")

                with ui.card().classes("form-card w-full p-5 gap-2"):
                    ui.label("Required Information").classes("font-semibold")

                    for required_text in [
                        "Item name",
                        "Category",
                        "Date acquired",
                        "Purchase price",
                    ]:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle").classes(
                                "text-green-600 text-lg"
                            )
                            ui.label(required_text).classes(
                                "text-sm text-slate-700"
                            )

        # Submission
        async def submit_form():
            success_label.visible = False
            error_label.visible = False

            for label in [
                name_error,
                category_error,
                date_error,
                amount_error,
                quantity_error,
            ]:
                label.visible = False

            # Clear previous field error styling.
            for field in [purchase_date_input, purchase_amount_input, quantity_input]:
                field.props(remove="error")

            name = (name_input.value or "").strip()
            category = category_select.value
            date_text = str(purchase_date_input.value or "")
            purchase_amount = purchase_amount_input.value

            # Validate item name and category.
            if not name:
                name_error.text = "Item name is required."
                name_error.visible = True

            if not category:
                category_error.text = "Please select a category."
                category_error.visible = True

            # Validate date.
            try:
                acquired_date = date.fromisoformat(date_text)
                if acquired_date > date.today():
                    raise ValueError("future")
            except (ValueError, TypeError):
                date_error.text = "Enter a valid date that is not in the future."
                date_error.visible = True
                purchase_date_input.props("error")

            # Validate purchase price.
            try:
                if purchase_amount is None or str(purchase_amount).strip() == "":
                    raise ValueError("required")

                purchase_amount = float(purchase_amount)

                if purchase_amount < 0:
                    raise ValueError("negative")

            except (ValueError, TypeError):
                amount_error.text = "Enter a valid purchase price of $0 or more."
                amount_error.visible = True
                purchase_amount_input.props("error")

            try:
                quantity = float(quantity_input.value)
                if quantity < 1 or not quantity.is_integer():
                    raise ValueError
            except (TypeError, ValueError):
                quantity_error.text = "Quantity must be a whole number of at least 1."
                quantity_error.visible = True
                quantity_input.props("error")

            if any(
                label.visible
                for label in [
                    name_error,
                    category_error,
                    date_error,
                    amount_error,
                    quantity_error,
                ]
            ):
                error_label.text = "Please correct the highlighted fields."
                error_label.visible = True
                return

            manual_value = manual_value_input.value
            if manual_value is not None:
                try:
                    manual_value = float(manual_value)
                    if manual_value < 0:
                        error_label.text = "Manual value cannot be negative."
                        error_label.visible = True
                        return
                except (TypeError, ValueError):
                    error_label.text = "Enter a valid manual value."
                    error_label.visible = True
                    return

            form_data = {
                "name": name,
                "category": category,
                "purchase_date": date_text,
                "purchase_amount": purchase_amount,
                "description": description_input.value or "",
                "brand": brand_input.value or "",
                "model_number": model_input.value or "",
                "serial_number": serial_input.value or "",
                "condition": condition_select.value or "unknown",
                "quantity": int(quantity),
                "manual_value": (
                    manual_value if manual_value is not None else ""
                ),
                "notes": notes_input.value or "",
            }

            try:
                session = authenticated_session()

                response = session.post(
                    f"{BACKEND_URL}/api/item/{item_id}/edit/",
                    data=form_data,
                    headers=csrf_headers(session),
                    timeout=10,
                )

                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {}

                if response.ok and response_data.get("success", True):
                    ui.notify("Item updated successfully.", type="positive")
                    ui.timer(
                        1.0,
                        lambda: ui.navigate.to("/inventory"),
                        once=True,
                    )
                    return

                server_errors = response_data.get("errors", {})
                field_labels = {
                    "name": name_error,
                    "category": category_error,
                    "purchase_date": date_error,
                    "purchase_amount": amount_error,
                    "quantity": quantity_error,
                }

                for field, label in field_labels.items():
                    if field in server_errors:
                        message = server_errors[field]
                        if isinstance(message, list):
                            message = message[0] if message else "Invalid value."
                        label.text = str(message)
                        label.visible = True

                        if field == "purchase_date":
                            purchase_date_input.props("error")
                        elif field == "purchase_amount":
                            purchase_amount_input.props("error")
                        elif field == "quantity":
                            quantity_input.props("error")

                error_label.text = response_data.get(
                    "error",
                    "Failed to update item. Please check the highlighted fields.",
                )
                error_label.visible = True

            except requests.RequestException as error:
                error_label.text = f"Connection error: {error}"
                error_label.visible = True

        # Bottom actions
        with ui.row().classes(
            "form-actions w-full items-center justify-between gap-4"
        ):
            ui.label("* Required field").classes("required-note")

            with ui.row().classes("items-center gap-3"):
                ui.button(
                    "Cancel",
                    on_click=lambda: ui.navigate.to("/inventory"),
                ).props(
                    "outline color=grey-7 no-caps"
                ).classes("px-5")

                ui.button(
                    "Save Changes",
                    icon="save",
                    on_click=submit_form,
                ).props(
                    "unelevated color=primary no-caps"
                ).classes("px-6 py-2 rounded-lg")

