import requests
import os
from nicegui import ui
from datetime import datetime

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


async def load_item_data(item_id: str) -> dict:
    """Fetch item data and available categories"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/item/{item_id}/edit/",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return {
                'item': data.get('item', {}),
                'categories': data.get('categories', []),
            }
        return {'item': {}, 'categories': []}
    except requests.RequestException as e:
        print(f"Error loading item: {e}")
        return {'item': {}, 'categories': []}


@ui.page("/edit-item/{item_id}")
async def edit_item_page(item_id: str):
    """Page for editing an existing item"""
    
    # Load item data
    data = await load_item_data(item_id)
    item = data.get('item', {})
    categories = data.get('categories', [])
    categories_dict = {cat['id']: cat['name'] for cat in categories}
    
    if not item:
        with ui.column().classes("w-full h-screen items-center justify-center"):
            ui.label("Item not found").classes("text-xl text-red-600")
        return
    
    # State for form
    errors = {}
    
    # Header
    with ui.header().classes("h-16 bg-white border-b"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.back()).props("flat round")
        ui.label(f"Edit {item.get('name', 'Item')}").classes("text-xl font-bold ml-4")
    
    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
        
        # Success message
        success_label = ui.label().classes("text-green-600 font-semibold hidden")
        
        # Error message
        error_label = ui.label().classes("text-red-600 font-semibold hidden")
        
        # Form sections
        with ui.card().classes("w-full"):
            ui.label("Required Information").classes("text-lg font-bold mb-4")
            
            with ui.column().classes("gap-4"):
                # Name
                name_input = ui.input(
                    label="Item Name *",
                    value=item.get('name', ''),
                    placeholder="Enter item name"
                ).classes("w-full")
                name_error = ui.label().classes("text-red-500 text-sm hidden")
                
                # Category
                category_select = ui.select(
                    label="Category *",
                    options=categories_dict,
                    value=item.get('category_id'),
                ).classes("w-full")
                category_error = ui.label().classes("text-red-500 text-sm hidden")
                
                # Purchase Date
                purchase_date_value = item.get('purchase_date')
                if purchase_date_value:
                    purchase_date_value = datetime.fromisoformat(purchase_date_value).date()
                else:
                    purchase_date_value = datetime.now().date()
                
                ui.label("Date Acquired *")
                purchase_date_input = ui.date(
                    value=purchase_date_value
                ).classes("w-full")
                date_error = ui.label().classes("text-red-500 text-sm hidden")

                # Purchase Amount
                purchase_amount_input = ui.number(
                    label="Purchase Price ($) *",
                    value=float(item.get('purchase_amount', 0)) if item.get('purchase_amount') else 0,
                    placeholder="0.00",
                    min=0,
                    step=0.01,
                ).classes("w-full")
                amount_error = ui.label().classes("text-red-500 text-sm hidden")
        
        # Additional fields
        with ui.card().classes("w-full"):
            ui.label("Additional Information").classes("text-lg font-bold mb-4")
            
            with ui.column().classes("gap-4"):
                # Description
                description_input = ui.textarea(
                    label="Description",
                    value=item.get('description', ''),
                    placeholder="Add any details about this item"
                ).classes("w-full h-24")
                
                # Brand
                brand_input = ui.input(
                    label="Brand",
                    value=item.get('brand', ''),
                    placeholder="Brand name"
                ).classes("w-full")
                
                # Model Number
                model_input = ui.input(
                    label="Model Number",
                    value=item.get('model_number', ''),
                    placeholder="Model number"
                ).classes("w-full")
                
                # Serial Number
                serial_input = ui.input(
                    label="Serial Number",
                    value=item.get('serial_number', ''),
                    placeholder="Serial number"
                ).classes("w-full")
                
                # Condition
                condition_select = ui.select(
                    label="Condition",
                    options={
                        'new': 'New',
                        'like_new': 'Like New',
                        'used': 'Used',
                        'damaged': 'Damaged',
                        'unknown': 'Unknown',
                    },
                    value=item.get('condition', 'unknown'),
                ).classes("w-full")
                
                # Quantity
                quantity_input = ui.number(
                    label="Quantity",
                    value=item.get('quantity', 1),
                    min=1,
                ).classes("w-full")
                
                # Manual Value
                manual_value_input = ui.number(
                    label="Manual Valuation ($)",
                    value=float(item.get('manual_value', 0)) if item.get('manual_value') else None,
                    placeholder="Optional: Set a custom value",
                    min=0,
                    step=0.01,
                ).classes("w-full")
                
                # Notes
                notes_input = ui.textarea(
                    label="Notes",
                    value=item.get('notes', ''),
                    placeholder="Any additional notes"
                ).classes("w-full h-20")
        
        # Submit button
        async def submit_form():
            nonlocal errors
            
            # Clear previous messages
            error_label.visible = False
            success_label.visible = False
            for label in [name_error, category_error, date_error, amount_error]:
                label.visible = False
            
            # Collect form data
            form_data = {
                'name': name_input.value.strip(),
                'category': category_select.value,
                'purchase_date': str(purchase_date_input.value) if purchase_date_input.value else '',
                'purchase_amount': purchase_amount_input.value,
                'description': description_input.value,
                'brand': brand_input.value,
                'model_number': model_input.value,
                'serial_number': serial_input.value,
                'condition': condition_select.value,
                'quantity': quantity_input.value,
                'manual_value': manual_value_input.value if manual_value_input.value else '',
                'notes': notes_input.value,
            }
            
            try:
                response = requests.post(
                    f"{BACKEND_URL}/api/item/{item_id}/edit/",
                    data=form_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    success_message = data.get('message', 'Item updated successfully!')
                    success_label.set_text(success_message)
                    success_label.visible = True
                    
                    # Redirect after 1.5 seconds
                    ui.timer(1.5, lambda: ui.navigate.to("/"))
                else:
                    data = response.json()
                    errors = data.get('errors', {})
                    
                    # Display field errors
                    if 'name' in errors:
                        name_error.set_text(errors['name'])
                        name_error.visible = True
                    if 'category' in errors:
                        category_error.set_text(errors['category'])
                        category_error.visible = True
                    if 'purchase_date' in errors:
                        date_error.set_text(errors['purchase_date'])
                        date_error.visible = True
                    if 'purchase_amount' in errors:
                        amount_error.set_text(errors['purchase_amount'])
                        amount_error.visible = True
                    
                    # Display general error
                    error_msg = data.get('error', 'Failed to update item. Please check the errors below.')
                    if errors and not error_msg.startswith('Failed'):
                        error_msg = "Please correct the errors below."
                    error_label.set_text(error_msg)
                    error_label.visible = True
            
            except requests.RequestException as e:
                error_label.set_text(f"Connection error: {str(e)}")
                error_label.visible = True
        
        # Button row
        with ui.row().classes("w-full gap-4 justify-end mt-6"):
            ui.button("Cancel", on_click=lambda: ui.navigate.back()).props("flat")
            ui.button("Save Changes", on_click=submit_form).props("unelevated").classes("bg-blue-600 text-white")
