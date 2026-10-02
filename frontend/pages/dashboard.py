import os
import requests
from nicegui import app, ui
from backend_client import BACKEND_URL, authenticated_session, csrf_headers


# COVERWORTH DASHBOARD
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
# ------------------------------------------------------------------
# DATA FETCHING FROM BACKEND
# ------------------------------------------------------------------

async def load_dashboard_data(cookies):
    """Fetch dashboard summary using this browser's Django session."""
    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/dashboard/",
            timeout=5,
        )
        if response.status_code == 401:
            return None
        response.raise_for_status()
        data = response.json()
        return {
            "summary": data.get("summary", {}),
            "category_data": data.get("category_data", []),
            "recent_items": data.get("recent_items", []),
            "inventory_id": data.get("inventory_id"),
        }
    except requests.RequestException as e:
        print(f"Error loading dashboard: {e}")
        return {
            "summary": {
                "total_items": 0,
                "estimated_value": 0,
                "purchase_value": 0,
                "items_needing_attention": 0,
            },
            "category_data": [],
            "recent_items": [],
            "inventory_id": None,
        }


def show_login_page(error_message=""):
    with ui.column().classes("w-full min-h-screen items-center justify-center p-6"):
        with ui.card().classes("w-full max-w-md p-8 gap-5"):
            ui.label("CoverWorth").classes("text-3xl font-bold text-primary")
            ui.label("Sign in to your account").classes("text-lg")

            username = ui.input("Username").props("outlined autocomplete=username").classes("w-full")
            password = ui.input("Password", password=True).props(
                "outlined autocomplete=current-password"
            ).classes("w-full")
            error = ui.label(error_message).classes("text-negative")

            async def submit_login():
                session = requests.Session()
                try:
                    response = session.post(
                        f"{BACKEND_URL}/api/auth/login/",
                        json={"username": username.value, "password": password.value},
                        headers=csrf_headers(session),
                        timeout=5,
                    )
                    if response.status_code == 401:
                        error.text = "Invalid username or password."
                        return
                    response.raise_for_status()
                except requests.RequestException:
                    error.text = "Could not connect to the server. Try again."
                    return

                app.storage.user["auth_cookies"] = session.cookies.get_dict()
                app.storage.user["username"] = response.json()["username"]
                ui.navigate.to("/")

            ui.button("Sign in", on_click=submit_login, icon="login").props(
                "unelevated color=primary no-caps"
            ).classes("w-full")


async def sign_out():
    session = authenticated_session()
    try:
        response = session.post(
            f"{BACKEND_URL}/api/auth/logout/",
            headers=csrf_headers(session),
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException:
        ui.notify("The server could not confirm sign-out.", type="negative")
    app.storage.user.clear()
    ui.navigate.to("/")

# ------------------------------------------------------------------
# GLOBAL STYLING
# ------------------------------------------------------------------

ui.add_css("""
    body {
        background: #f3f8fb;
        color: #0f172a;
        font-family: Inter, Roboto, Arial, sans-serif;
    }

    .nicegui-content {
        padding: 0 !important;
        background-color: #f3f8fb !important;

    }

    /* ----------------------------------------------------------
       Sidebar
       ---------------------------------------------------------- */

    .sidebar {
        background: #203756 !important;
        color: #ffffff;
    }

    .q-drawer.sidebar,
    .q-drawer.sidebar .q-drawer__content {
        background: #203756 !important;
    }

    .sidebar-logo {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: #ffffff !important;
    }

    .nav-item {
        width: 100%;
        min-height: 48px;
        border-radius: 8px;
        color: #ffffff !important;
        padding: 0 14px;
    }

    .nav-item:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .nav-item-active {
        background: #1769c2;
        color: white;
    }

    /* ----------------------------------------------------------
       Header
       ---------------------------------------------------------- */

    .q-header.top-header {
        background-color: #eff5f9 !important;
        color: #0f172a;
        border-bottom: 1px solid #dce3ec;
        box-shadow: none;
    }

    /* ----------------------------------------------------------
       Cards
       ---------------------------------------------------------- */

    .dashboard-card {
        background: white;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .stat-value {
        font-size: 30px;
        font-weight: 700;
        line-height: 1.1;
    }

    .stat-label {
        font-size: 15px;
        color: #64748b;
    }

    .section-title {
        font-size: 18px;
        font-weight: 700;
        color: #0f172a;
    }

    .muted {
        color: #64748b;
    }

    .recent-item:hover {
        background: #f8fafc;
    }

    .attention-card {
        background: #fff7f7;
        border: 1px solid #fecaca;
        border-radius: 12px;
    }

    /* Makes main content look good on larger screens */
    .dashboard-container {
        width: 100%;
        max-width: 1450px;
        margin: 0 auto;
    }
""", shared=True)


# ------------------------------------------------------------------
# REUSABLE COMPONENTS
# ------------------------------------------------------------------

def navigation_item(
    label: str,
    icon: str,
    route: str | None = None,
    active: bool = False,
) -> None:

    classes = "nav-item items-center gap-3"

    if active:
        classes += " nav-item-active"

    def Navigate():
        if route:
            ui.navigate.to(route)
        else:
            ui.notify(f"{label} page has not been implemented yet.")

    with ui.row().classes(classes).on("click", Navigate):

        ui.icon(icon).classes("text-xl").style(
            "color: #ffffff !important;"
        )

        ui.label(label).classes("text-sm font-medium").style(
            "color: #ffffff !important;"
        )


def stat_card(
    title: str,
    value: str,
    icon: str,
    icon_color: str = "text-blue-600",
    change_text: str | None = None,
) -> None:

    with ui.card().classes(
        "dashboard-card w-full min-h-[175px] p-6"
    ):

        with ui.row().classes(
            "w-full items-start justify-between"
        ):

            with ui.column().classes("gap-3"):

                ui.label(value).classes("stat-value")

                ui.label(title).classes("stat-label")

                if change_text:
                    with ui.row().classes(
                        "items-center gap-1 "
                        "bg-green-50 text-green-700 "
                        "px-3 py-1 rounded-full"
                    ):
                        ui.icon("trending_up").classes("text-sm")
                        ui.label(change_text).classes(
                            "text-xs font-medium"
                        )

            with ui.element("div").classes(
                "bg-blue-50 rounded-xl "
                "w-14 h-14 flex items-center justify-center"
            ):

                ui.icon(icon).classes(
                    f"text-3xl {icon_color}"
                )


@ui.refreshable
def value_by_category_card(category_data) -> None:
    selected_categories = app.storage.user.get("selected_categories", {})
    if not selected_categories and category_data:
        selected_categories = {cat["name"]: True for cat in category_data}
        app.storage.user["selected_categories"] = selected_categories

    # Calculate total of ONLY the currently selected categories
    active_total = sum(
        cat["value"] for cat in category_data 
        if selected_categories.get(cat["name"], True)
    )

    # Explicit shared color palette for both chart slices and legend swatches
    colors = ["#5470c6", "#91cc75", "#334155", "#fac858", "#73c0de", "#3ba272"]

    with ui.card().classes("dashboard-card w-full p-6 h-full"):
        
        # Header
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("Value by Category").classes("section-title")
            ui.button(icon="more_vert").props("flat round dense color=grey-7")

        # Main Layout: Chart on the left, Custom Legend on the right
        with ui.row().classes("w-full items-center justify-between gap-4"):
            
            # Chart container with center text overlay
            with ui.element('div').classes("relative w-[55%] h-[300px]"):
                
                # Build chart data with explicit matching colors
                chart_data = [
                    {
                        "value": cat["value"] if selected_categories.get(cat["name"], True) else 0,
                        "name": cat["name"],
                        "itemStyle": {"color": colors[idx % len(colors)]}
                    }
                    for idx, cat in enumerate(category_data)
                ]

                chart_options = {
                    "tooltip": {
                        "trigger": "item",
                        "formatter": "{b}: ${c} ({d}%)",
                    },
                    "series": [
                        {
                            "name": "Category Value",
                            "type": "pie",
                            "radius": ["48%", "72%"],
                            "center": ["50%", "50%"],
                            "avoidLabelOverlap": True,
                            "itemStyle": {
                                "borderColor": "#ffffff",
                                "borderWidth": 2,
                            },
                            "label": {"show": False},
                            "data": chart_data,
                        }
                    ],
                }
                
                ui.echart(chart_options).classes("w-full h-full absolute inset-0")
                
                # Center Text Overlay showing the active sum dynamically
                with ui.element('div').classes("absolute inset-0 flex flex-col items-center justify-center pointer-events-none"):
                    ui.label(f"${active_total:,.0f}").classes("text-xl font-bold text-slate-900")
                    ui.label("Total Value").classes("text-xs text-slate-500")

            # Custom Legend using the exact same `colors` array
            with ui.column().classes("w-[38%] gap-2 justify-center"):
                ui.label("CATEGORIES").classes("text-xs font-bold text-slate-400 uppercase tracking-wider mb-1")
                
                for idx, cat in enumerate(category_data):
                    name = cat["name"]
                    is_active = selected_categories.get(name, True)
                    color = colors[idx % len(colors)]
                    
                    def make_click(cat_name=name):
                        def toggle():
                            updated_selection = dict(
                                app.storage.user.get("selected_categories", {})
                            )
                            updated_selection[cat_name] = not updated_selection.get(
                                cat_name,
                                True,
                            )
                            app.storage.user["selected_categories"] = updated_selection
                            value_by_category_card.refresh()
                        return toggle

                    with ui.row().classes("items-center gap-2.5 cursor-pointer py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors").on('click', make_click()):
                        opacity_class = "opacity-100" if is_active else "opacity-30"
                        ui.element('div').classes(f"w-3.5 h-3.5 rounded-[3px] {opacity_class}").style(f"background-color: {color};")
                        
                        text_class = "text-sm font-medium text-slate-700" if is_active else "text-sm font-medium text-slate-400 line-through"
                        ui.label(name).classes(text_class)



def recent_items_card(recent_items) -> None:

    with ui.card().classes(
        "dashboard-card w-full p-6 h-full"
    ):

        with ui.row().classes(
            "w-full items-center justify-between mb-2"
        ):

            ui.label("Recent Items").classes(
                "section-title"
            )

            ui.button(
                "View all",
                icon="chevron_right",
            ).props(
                "flat color=primary no-caps"
            )

        for index, item in enumerate(recent_items):

            with ui.row().classes(
                "recent-item w-full items-center "
                "justify-between py-3 px-2 rounded-lg"
            ):

                with ui.row().classes(
                    "items-center gap-3"
                ):

                    with ui.element("div").classes(
                        "w-11 h-11 bg-slate-100 "
                        "rounded-lg flex items-center "
                        "justify-center"
                    ):
                        ui.icon(item.get("icon", "inventory_2")).classes(
                            "text-2xl text-slate-600"
                        )

                    with ui.column().classes("gap-0"):

                        ui.link(
                            item["name"],
                            f"/edit-item/{item['public_id']}"
                        ).classes(
                            "text-sm font-semibold"
                        )

                        ui.label(
                            item["category"]
                        ).classes(
                            "text-xs muted"
                        )

                with ui.row().classes(
                    "items-center gap-4"
                ):

                    with ui.column().classes(
                        "items-end gap-0"
                    ):

                        ui.label(
                            f'${item["value"]:,.0f}'
                        ).classes(
                            "text-sm font-semibold"
                        )

                        ui.label(
                            item["date"]
                        ).classes(
                            "text-xs muted"
                        )

                    ui.button(
                        icon="more_vert",
                        on_click=lambda item_id=item.get('public_id'): ui.navigate.to(f"/edit-item/{item_id}")
                    ).props(
                        "flat round dense color=grey-7"
                    )

            if index < len(recent_items) - 1:
                ui.separator()


def attention_banner(dashboard_data) -> None:

    with ui.card().classes(
        "attention-card w-full p-5"
    ):

        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            with ui.row().classes(
                "items-center gap-4"
            ):

                ui.icon(
                    "warning_amber"
                ).classes(
                    "text-4xl text-red-600"
                )

                with ui.column().classes("gap-0"):

                    ui.label(
                        f'{dashboard_data["items_needing_attention"]} '
                        "items need attention"
                    ).classes(
                        "text-red-700 font-bold text-base"
                    )

                    ui.label(
                        "These items have outdated valuations."
                    ).classes(
                        "text-sm text-slate-600"
                    )

            ui.button(
                "Review",
                icon="arrow_forward",
            ).props(
                "flat color=primary no-caps"
            ).classes(
                "font-semibold"
            )


# ------------------------------------------------------------------
# PAGE LAYOUT
# ------------------------------------------------------------------

@ui.page("/")
async def dashboard_page():
    cookies = app.storage.user.get("auth_cookies")
    if not cookies:
        show_login_page()
        return

    api_data = await load_dashboard_data(cookies)
    if api_data is None:
        app.storage.user.clear()
        show_login_page("Your session expired. Please sign in again.")
        return

    dashboard_data = api_data["summary"]
    category_data = api_data["category_data"]
    recent_items = api_data["recent_items"]
    inventory_id = api_data.get("inventory_id")

    # --------------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------------

    with ui.left_drawer(
        value=True,
        top_corner=True,
        bottom_corner=True,
    ).props(
        "width=230 breakpoint=800"
    ).classes(
        "sidebar p-0"
    ).style(
        "background-color: #203756 !important;"
    ) as drawer:

        # Logo
        with ui.row().classes(
            "w-full items-center gap-3 px-5 py-6"
        ):

            with ui.element("div").classes(
                "w-10 h-10 bg-blue-500/20 "
                "rounded-xl flex items-center justify-center"
            ):
                ui.icon(
                    "inventory_2"
                ).classes(
                    "text-3xl text-blue-400"
                )

            ui.label(
                "CoverWorth"
            ).classes(
                "sidebar-logo"
            ).style(
                "color: #ffffff !important;"
            )

        # Navigation
        with ui.column().classes(
            "w-full px-3 gap-2"
        ):

            navigation_item(
                "Dashboard",
                "home",
                route="/",
                active=True,
            )

            navigation_item(
                "Inventory",
                "inventory_2",
                route="/inventory",
            )

            navigation_item(
                "Collections",
                "folder",
            )

            navigation_item(
                "Valuations",
                "analytics",
            )

            navigation_item(
                "Reports",
                "description",
            )

            ui.separator().classes(
                "my-3 opacity-20"
            )

            navigation_item(
                "Settings",
                "settings",
            )

    # --------------------------------------------------------------
    # HEADER
    # --------------------------------------------------------------

    with ui.header().classes(
        "top-header h-[68px] "
        "items-center px-5"
    ).style(
        "background-color: #eff5f9 !important; color: #0f172a !important;"
    ):

        ui.button(
            icon="menu",
            on_click=drawer.toggle,
        ).props(
            "flat round color=grey-8"
        )

        ui.space()

        # Search box
        ui.input(
            placeholder="Search items..."
        ).props(
            "outlined dense rounded"
        ).classes(
            "w-[420px] max-w-[45vw]"
        ).props(
            'prepend-icon="search"'
        )

        ui.space()

        ui.button(
            icon="notifications_none"
        ).props(
            "flat round color=grey-8"
        )

        ui.avatar(
            "KM",
            color="primary",
            text_color="white",
        ).classes(
            "ml-2"
        )

        ui.label(app.storage.user.get("username", "User")).classes(
            "font-medium hidden md:block"
        )

        ui.button("Sign out", on_click=sign_out, icon="logout").props(
            "flat no-caps color=grey-8"
        )

    # --------------------------------------------------------------
    # MAIN DASHBOARD CONTENT
    # --------------------------------------------------------------

    with ui.column().classes(
        "dashboard-container p-7 gap-5"
    ):

        # Dashboard title
        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            with ui.column().classes("gap-0"):

                ui.label(
                    "Dashboard"
                ).classes(
                    "text-4xl font-bold tracking-tight"
                )

                ui.label(
                    "Your collection at a glance"
                ).classes(
                    "text-base muted"
                )

            ui.button(
                "Add Item",
                icon="add",
                on_click=lambda: ui.navigate.to(f"/add-item/{inventory_id}"),
            ).props(
                "unelevated color=primary no-caps"
            ).classes(
                "px-5 py-2 rounded-lg"
            )

        # ----------------------------------------------------------
        # SUMMARY CARDS
        # ----------------------------------------------------------

        with ui.grid(
            columns=3
        ).classes(
            "w-full gap-4 "
            "max-lg:grid-cols-1"
        ):

            stat_card(
                title="Total Items",
                value=f'{dashboard_data["total_items"]:,}',
                icon="inventory_2",
            )

            stat_card(
                title="Estimated Value",
                value=(
                    f'${dashboard_data["estimated_value"]:,.0f}'
                ),
                icon="trending_up",
                icon_color="text-green-600",
                change_text="+12% from last month",
            )

            stat_card(
                title="Purchase Value",
                value=(
                    f'${dashboard_data["purchase_value"]:,.0f}'
                ),
                icon="sell",
                change_text="+8% from last month",
            )

        # ----------------------------------------------------------
        # CHART + RECENT ITEMS
        # ----------------------------------------------------------

        with ui.grid().classes(
            "w-full grid-cols-[1.05fr_1fr] "
            "gap-4 max-lg:grid-cols-1"
        ):

            value_by_category_card(category_data)

            recent_items_card(recent_items)

        # ----------------------------------------------------------
        # ATTENTION / REVIEW BANNER
        # ----------------------------------------------------------

        attention_banner(dashboard_data)







