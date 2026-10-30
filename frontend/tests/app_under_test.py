"""Entry point for the NiceGUI user simulation.

Same page set as main.py. The test fixtures reset NiceGUI's routes before
every test, so each page module is reloaded to register its @ui.page() route
again. NiceGUI 3.x requires the main file to call ui.run(); under pytest that
call only records the run config and does not start a server.
"""

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

ui.run(reload=False)