import requests
from nicegui import app, run, ui

from backend_client import BACKEND_URL, authenticated_session, csrf_headers
from utilities.attachments import attachment_url
from utilities.inventory_search import SearchSessionExpired, search_items
from utilities.inventory_switcher import InventoryApiError, show_inventory_switcher

#TODO : Replace user related things with dynamic username from backend

ui.add_css("""
    .sidebar,
    .q-drawer.sidebar,
    .q-drawer.sidebar .q-drawer__content {
        background: #203756 !important;
        color: #ffffff;
    }

    .sidebar-logo {
        color: #ffffff !important;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    .nav-item {
        width: 100%;
        min-height: 48px;
        border-radius: 8px;
        color: #ffffff !important;
        padding: 0 14px;
        cursor: pointer;
    }

    .nav-item:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .nav-item-active {
        background: #1769c2;
        color: #ffffff;
    }

    .q-header.top-header {
        background: #eff5f9 !important;
        color: #0f172a;
        border-bottom: 1px solid #dce3ec;
        box-shadow: none;
    }

    .page-content-frame.page-content-frame {
        box-sizing: border-box;
        width: 100%;
        max-width: 1500px;
        min-height: calc(100vh - 116px);
        margin: 24px auto;
        border: 1px solid #dce3ec;
        border-radius: 12px;
        background: #ffffff;
    }

    .global-search-results {
        position: absolute;
        top: 100%;
        left: 0;
        width: 100%;
        margin-top: 4px;
        z-index: 3000;
        max-height: 420px;
        overflow-y: auto;
        border: 1px solid #dce3ec;
        border-radius: 8px;
        background: #ffffff;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
    }

    .global-search-result:hover {
        background: #eff5f9;
        cursor: pointer;
    }

    @media (max-width: 1550px) {
        .page-content-frame.page-content-frame {
            width: calc(100% - 48px);
        }
    }
""", shared=True)


def _initials(username: str) -> str:
    """First two letters of the username, uppercased."""
    letters = [c for c in username if c.isalpha()]
    return "".join(letters[:2]).upper() or "?"


async def _sign_out() -> None:
    session = authenticated_session()

    try:
        response = session.post(
            f"{BACKEND_URL}/api/auth/logout/",
            headers=csrf_headers(session),
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException:
        ui.notify(
            "The server could not confirm sign-out.",
            type="negative",
        )

    app.storage.user.pop("auth_cookies", None)
    app.storage.user.pop("username", None)
    ui.navigate.to("/")


def _navigation_item(
    label: str,
    icon: str,
    route: str | None = None,
    active: bool = False,
) -> None:
    classes = "nav-item items-center gap-3"
    if active:
        classes += " nav-item-active"

    def navigate() -> None:
        if route:
            ui.navigate.to(route)
        else:
            ui.notify(f"{label} page has not been implemented yet.")

    with ui.row().classes(classes).on("click", navigate):
        ui.icon(icon).classes("text-xl")
        ui.label(label).classes("text-sm font-medium")


def _build_global_search() -> None:
    with ui.element("div").classes("relative w-[520px] max-w-[50vw]"):
        search = ui.input(
            placeholder="Search items, categories, or locations..."
        ).props(
            "outlined dense rounded clearable debounce=300 prepend-icon=search"
        ).classes("w-full")

        results = ui.column().classes("global-search-results gap-0 p-1")
        results.set_visibility(False)

        def close() -> None:
            results.set_visibility(False)

        latest = {"request": 0}

        def open_item(item: dict) -> None:
            close()
            search.set_value("")
            ui.navigate.to(f"/item/{item['public_id']}")

        async def run_search(query: str) -> None:
            query = (query or "").strip()
            latest["request"] += 1
            request_id = latest["request"]
            if len(query) < 2:
                results.clear()
                close()
                return

            matches: list[dict] | None
            try:
                matches, cookies = await run.io_bound(
                    search_items,
                    dict(app.storage.user.get("auth_cookies", {})),
                    query,
                )
            except SearchSessionExpired:
                close()
                app.storage.user.pop("auth_cookies", None)
                app.storage.user.pop("username", None)
                ui.notify("Your session expired. Please sign in again.", type="warning")
                ui.navigate.to("/")
                return
            except (requests.RequestException, InventoryApiError, ValueError):
                matches = None
            else:
                app.storage.user["auth_cookies"] = cookies

            # A newer keystroke fired another search; drop this stale response.
            if request_id != latest["request"]:
                return

            results.clear()
            with results:
                if matches is None:
                    ui.label("Search is unavailable right now").classes(
                        "text-sm text-negative p-3"
                    )
                elif not matches:
                    ui.label("No items found").classes("text-sm text-grey-6 p-3")
                for item in (matches or [])[:8]:
                    with ui.row().classes(
                        "global-search-result w-full items-center gap-3 px-3 py-2 rounded"
                    ).on("click", lambda _, i=item: open_item(i)):
                        photo = attachment_url(item.get("primary_photo_url") or "")
                        if photo:
                            ui.image(photo).classes("w-10 h-10 rounded flex-none")
                        else:
                            with ui.element("div").classes(
                                "w-10 h-10 rounded bg-grey-2 flex-none "
                                "flex items-center justify-center"
                            ):
                                ui.icon("inventory_2").classes("text-grey-6")
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(item["name"]).classes("text-sm font-medium")
                            details = " · ".join(
                                part for part in (item.get("category"), item.get("location")) if part
                            )
                            if details:
                                ui.label(details).classes("text-xs text-grey-6")
            results.set_visibility(True)

        async def on_change(e) -> None:
            await run_search(e.value)

        async def on_enter() -> None:
            # Enter toggles the results panel: close it if open, otherwise search.
            if results.visible:
                close()
            else:
                await run_search(search.value)

        search.on_value_change(on_change)
        search.on("keydown.enter", on_enter)
        search.on("keydown.escape", close)
        # Small delay so clicks on a result still register before the panel closes.
        search.on("blur", lambda: ui.timer(0.2, close, once=True))


def build_app_shell(
    active_page: str,
    username: str = "Kevin M.",
) -> None:
    with ui.left_drawer(
        value=True,
        top_corner=True,
        bottom_corner=True,
    ).props("width=230 breakpoint=800").classes("sidebar p-0") as drawer:
        with ui.row().classes("w-full items-center gap-3 px-5 py-6"):
            with ui.element("div").classes(
                "w-10 h-10 bg-blue-500/20 rounded-xl "
                "flex items-center justify-center"
            ):
                ui.icon("inventory_2").classes("text-3xl text-blue-400")

            ui.label("CoverWorth").classes("sidebar-logo")

        with ui.column().classes("w-full px-3 gap-2"):
            _navigation_item("Dashboard", "home", "/dashboard", active_page == "Dashboard")
            _navigation_item("Inventory", "inventory_2", "/inventory", active_page == "Inventory")
            _navigation_item("Categories", "folder", "/categories", active_page == "Categories")
            _navigation_item("Valuations", "analytics", "/valuations", active_page == "Valuations")
            _navigation_item("Reports", "description", "/reports", active_page == "Reports")
            ui.separator().classes("my-3 opacity-20")
            _navigation_item("Settings", "settings", "/settings", active_page == "Settings")

    with ui.header().classes("top-header h-[68px] items-center px-5"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round color=grey-8")
        show_inventory_switcher(active_page)
        ui.space()
        _build_global_search()
        ui.space()
        ui.avatar(_initials(username), color="primary", text_color="white").classes("ml-2")
        ui.label(username).classes("font-medium hidden md:block")

        ui.button("Sign out", on_click=_sign_out, icon="logout").props(
            "flat no-caps color=grey-8"
        )