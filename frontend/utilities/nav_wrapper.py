from collections.abc import Callable

from nicegui import ui


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

    @media (max-width: 1550px) {
        .page-content-frame.page-content-frame {
            width: calc(100% - 48px);
        }
    }
""", shared=True)


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


def build_app_shell(
    active_page: str,
    username: str = "Kevin M.",
    on_sign_out: Callable[[], object] | None = None,
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
            _navigation_item("Dashboard", "home", "/", active_page == "Dashboard")
            _navigation_item("Inventory", "inventory_2", "/inventory", active_page == "Inventory")
            _navigation_item("Collections", "folder", active=active_page == "Collections")
            _navigation_item("Valuations", "analytics", "/valuations", active_page == "Valuations")
            _navigation_item("Reports", "description", "/reports", active_page == "Reports")
            ui.separator().classes("my-3 opacity-20")
            _navigation_item("Settings", "settings", active=active_page == "Settings")

    with ui.header().classes("top-header h-[68px] items-center px-5"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round color=grey-8")
        ui.space()
        ui.input(
            placeholder="Search items, collections, or categories..."
        ).props(
            "outlined dense rounded prepend-icon=search"
        ).classes("w-[520px] max-w-[50vw]")
        ui.space()
        ui.button(icon="notifications_none").props("flat round color=grey-8")
        ui.avatar("KM", color="primary", text_color="white").classes("ml-2")
        ui.label(username).classes("font-medium hidden md:block")

        if on_sign_out:
            ui.button("Sign out", on_click=on_sign_out, icon="logout").props(
                "flat no-caps color=grey-8"
            )
        else:
            ui.button(icon="keyboard_arrow_down").props(
                "flat round dense color=grey-8"
            )
