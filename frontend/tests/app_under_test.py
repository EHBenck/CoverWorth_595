"""Entry point for the NiceGUI user simulation.

Same page set as main.py, without ui.run(). The test fixtures reset NiceGUI's
routes before every test, so each page module is reloaded to register its
@ui.page() route again.
"""

import importlib

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

register_attachment_routes()
