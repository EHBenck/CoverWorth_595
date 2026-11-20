"""Entry point for the NiceGUI user simulation.

Same page set as main.py. The test fixtures reset NiceGUI's routes before
every test, so each page module is reloaded to register its @ui.page() route
again. NiceGUI 3.x requires the main file to call ui.run(); under pytest that
call only records the run config and does not start a server.
"""

import importlib
import os

from nicegui import ui

import backend_client
import utilities.attachments
import utilities.inventory_management
import utilities.inventory_search
import utilities.inventory_switcher
import utilities.inventory_table
import utilities.location_management
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

# Reload order matters: backend_client first, so every module that does
# `from backend_client import BACKEND_URL` re-reads the test server's port.
PAGE_MODULES = [
    backend_client,
    utilities.attachments,
    utilities.inventory_switcher,
    utilities.inventory_management,
    utilities.location_management,
    utilities.inventory_search,
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


if "PYTEST_CURRENT_TEST" in os.environ:
    ui.run(reload=False, storage_secret="coverworth-test-secret")
