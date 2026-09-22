import os

import requests
from nicegui import ui


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


@ui.page("/")
async def home_page() -> None:
    status = ui.label("Checking backend...").classes("text-body1")

    async def check_backend() -> None:
        try:
            response = requests.get(f"{BACKEND_URL}/api/health/", timeout=3)
            response.raise_for_status()
            status.text = response.json().get("message", "Backend connected")
            status.classes(remove="text-negative")
            status.classes(add="text-positive")
        except (requests.RequestException, ValueError):
            status.text = "Backend connection failed"
            status.classes(remove="text-positive")
            status.classes(add="text-negative")

    with ui.column().classes("w-full max-w-3xl mx-auto items-center gap-6 p-8"):
        ui.label("CoverWorth").classes("text-5xl font-bold text-primary")
        ui.label("Inventory management, built in Python.").classes("text-xl")

        with ui.card().classes("w-full items-center gap-3"):
            ui.label("System status").classes("text-2xl font-semibold")
            status
            ui.button("Check again", on_click=check_backend, icon="refresh")

    await check_backend()


ui.run(
    host=os.getenv("NICEGUI_HOST", "127.0.0.1"),
    port=int(os.getenv("NICEGUI_PORT", "8080")),
    title="CoverWorth",
    reload=True,
)