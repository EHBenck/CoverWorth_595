from django.template import response
import requests
import os
from nicegui import ui
from datetime import datetime

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


async def load_categories(inventory_id: str) -> dict:
    """Fetch available categories for an inventory"""
    if not inventory_id or inventory_id == "None":
        return {}
        
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/inventory/{inventory_id}/add-item/",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            categories = data.get('categories', [])
            
            # Flexible mapping to catch id, public_id, or pk
            category_dict = {}
            for cat in categories:
                cat_id = str(cat.get('id') or cat.get('public_id') or cat.get('pk'))
                cat_name = cat.get('name') or cat.get('title')
                if cat_id and cat_name:
                    category_dict[cat_id] = cat_name
                    
            return category_dict
            
        return {}
    except requests.RequestException as e:
        print(f"Error loading categories: {e}")
        return {}


@ui.page("/add-item/{inventory_id}")
async def add_item_page(inventory_id: str):
    """Page for adding a new item to an inventory"""
    
    # Load categories
    categories = await load_categories(inventory_id)
    
    # State for form
    form_data = {
        'name': '',
        'category': None,
        'purchase_date': None,
        'purchase_amount': None,
        'description': '',
        'brand': '',
        'model_number': '',
        'serial_number': '',
        'condition': 'unknown',
        'quantity': 1,
        'manual_value': None,
        'notes': '',
    }
    
    errors = {}
    success_message = ""
    
    # Header
    with ui.header().classes("h-16 bg-white border-b"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.back()).props("flat round")
        ui.label("Add Item").classes("text-xl font-bold ml-4")
    
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
                    placeholder="Enter item name"
                ).classes("w-full")
                name_error = ui.label().classes("text-red-500 text-sm hidden")
                
                # Category
                category_select = ui.select(
                    label="Category *",
                    options=categories,
                ).classes("w-full")
                category_error = ui.label().classes("text-red-500 text-sm hidden")
                
                # Purchase Date
                ui.label("Date Acquired *")
                purchase_date_input = ui.date(
                    value=datetime.now().date()
                ).classes("w-full")
                date_error = ui.label().classes("text-red-500 text-sm hidden")

                # Purchase Amount
                purchase_amount_input = ui.number(
                    label="Purchase Price ($) *",
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
                    placeholder="Add any details about this item"
                ).classes("w-full").props("rows=3")
                
                # Brand
                brand_input = ui.input(
                    label="Brand",
                    placeholder="Brand name"
                ).classes("w-full")
                
                # Model Number
                model_input = ui.input(
                    label="Model Number",
                    placeholder="Model number"
                ).classes("w-full")
                
                # Serial Number
                serial_input = ui.input(
                    label="Serial Number",
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
                    value='unknown',
                ).classes("w-full")
                
                # Quantity
                quantity_input = ui.number(
                    label="Quantity",
                    value=1,
                    min=1,
                ).classes("w-full")
                
                # Manual Value
                manual_value_input = ui.number(
                    label="Manual Valuation ($)",
                    placeholder="Optional: Set a custom value",
                    min=0,
                    step=0.01,
                ).classes("w-full")
                
                # Notes
                notes_input = ui.textarea(
                    label="Notes",
                    placeholder="Any additional notes"
                ).classes("w-full").props("rows=3")
        
        # Submit button
        async def submit_form():
            nonlocal errors, success_message
            
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
                    f"{BACKEND_URL}/api/inventory/{inventory_id}/add-item/",
                    data=form_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    success_message = data.get('message', 'Item added successfully!')
                    success_label.set_text(success_message)
                    success_label.visible = True
                    
                    # Clear form
                    name_input.value = ""
                    category_select.value = None
                    description_input.value = ""
                    brand_input.value = ""
                    model_input.value = ""
                    serial_input.value = ""
                    condition_select.value = "unknown"
                    quantity_input.value = 1
                    manual_value_input.value = None
                    notes_input.value = ""
                    
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
                    error_msg = data.get('error', 'Failed to add item. Please check the errors below.')
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
            ui.button("Add Item", on_click=submit_form).props("unelevated").classes("bg-blue-600 text-white")
