import os
from nicegui import ui

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# Import all page modules to register their @ui.page() decorators
from pages.dashboard import dashboard_page
from pages.add_item import add_item_page
from pages.edit_item import edit_item_page
from pages.inventory import inventory_page

ui.run(
    host=os.getenv("NICEGUI_HOST", "127.0.0.1"),
    port=int(os.getenv("NICEGUI_PORT", "8080")),
    title="CoverWorth",
    favicon="📦",
    storage_secret=os.getenv(
        "NICEGUI_STORAGE_SECRET",
        "coverworth-development-storage-secret",
    ),
    reload=False,
)