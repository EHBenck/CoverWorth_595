
"""Entry point for NiceGUI integration tests."""

import importlib

from nicegui import ui

import backend_client
import utilities.inventory_table
import utilities.nav_wrapper

from utilities.attachments import register_attachment_routes

from pages import (
    add_item,
    categories,
    dashboard,
    edit_item,
    inventory,
    item_detail,
    register,
    reports,
    settings,
    valuations,
)

# NiceGUI's testing fixture resets registered routes between tests.
# Reload each module so its @ui.page() decorators run again.
PAGE_MODULES = [
    backend_client,
    utilities.nav_wrapper,
    utilities.inventory_table,
    dashboard,
    add_item,
    edit_item,
    inventory,
    item_detail,
    valuations,
    reports,
    categories,
    register,
    settings,
]

for module in PAGE_MODULES:
    importlib.reload(module)

# Register custom attachment routes after module reloads.
register_attachment_routes()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        reload=False,
        storage_secret="coverworth-test-secret",
        show=False,
    )
