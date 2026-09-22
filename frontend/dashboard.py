from nicegui import ui


# COVERWORTH DASHBOARD

# ------------------------------------------------------------------
# MOCK DATA
# Replace this later with API calls to Django.
# ------------------------------------------------------------------

dashboard_data = {
    "total_items": 128,
    "estimated_value": 24580,
    "purchase_value": 19200,
    "items_needing_attention": 5,
}


category_data = [
    {"name": "Electronics", "value": 7866},
    {"name": "Watches", "value": 4424},
    {"name": "Collectibles", "value": 3441},
    {"name": "Furniture", "value": 2949},
    {"name": "Sports", "value": 2458},
    {"name": "Other", "value": 3442},
]


recent_items = [
    {
        "name": "Canon EOS R6",
        "category": "Electronics",
        "value": 1850,
        "date": "Sep 10, 2026",
        "icon": "photo_camera",
    },
    {
        "name": "Seiko Prospex",
        "category": "Watches",
        "value": 725,
        "date": "Sep 9, 2026",
        "icon": "watch",
    },
    {
        "name": "MacBook Pro",
        "category": "Electronics",
        "value": 1250,
        "date": "Sep 8, 2026",
        "icon": "laptop_mac",
    },
    {
        "name": "Lake Painting",
        "category": "Art",
        "value": 475,
        "date": "Sep 7, 2026",
        "icon": "image",
    },
    {
        "name": "Leather Couch",
        "category": "Furniture",
        "value": 2100,
        "date": "Sep 6, 2026",
        "icon": "chair",
    },
]


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
""")


# ------------------------------------------------------------------
# REUSABLE COMPONENTS
# ------------------------------------------------------------------

def navigation_item(
    label: str,
    icon: str,
    active: bool = False,
) -> None:

    classes = "nav-item items-center gap-3"

    if active:
        classes += " nav-item-active"

    with ui.row().classes(classes):

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


def value_by_category_card() -> None:

    total = sum(category["value"] for category in category_data)

    with ui.card().classes(
        "dashboard-card w-full p-6 h-full"
    ):

        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            ui.label("Value by Category").classes(
                "section-title"
            )

            ui.button(icon="more_vert").props(
                "flat round dense color=grey-7"
            )

        chart_options = {
            "tooltip": {
                "trigger": "item",
                "formatter": "${c} ({d}%)",
            },
            "legend": {
                "orient": "vertical",
                "right": "3%",
                "top": "middle",
                "textStyle": {
                    "fontSize": 13,
                },
            },
            "series": [
                {
                    "name": "Category Value",
                    "type": "pie",
                    "radius": ["48%", "72%"],
                    "center": ["32%", "52%"],
                    "avoidLabelOverlap": True,
                    "itemStyle": {
                        "borderRadius": 3,
                        "borderColor": "#ffffff",
                        "borderWidth": 2,
                    },
                    "label": {
                        "show": False,
                    },
                    "emphasis": {
                        "label": {
                            "show": False,
                        }
                    },
                    "data": [
                        {
                            "value": category["value"],
                            "name": category["name"],
                        }
                        for category in category_data
                    ],
                }
            ],
            "graphic": [
                {
                    "type": "text",
                    "left": "23%",
                    "top": "45%",
                    "style": {
                        "text": f"${total:,.0f}",
                        "fontSize": 20,
                        "fontWeight": "bold",
                        "fill": "#0f172a",
                    },
                },
                {
                    "type": "text",
                    "left": "25%",
                    "top": "53%",
                    "style": {
                        "text": "Total Value",
                        "fontSize": 12,
                        "fill": "#64748b",
                    },
                },
            ],
        }

        ui.echart(chart_options).classes(
            "w-full h-[330px]"
        )


def recent_items_card() -> None:

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
                        ui.icon(item["icon"]).classes(
                            "text-2xl text-slate-600"
                        )

                    with ui.column().classes("gap-0"):

                        ui.label(
                            item["name"]
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
                        icon="more_vert"
                    ).props(
                        "flat round dense color=grey-7"
                    )

            if index < len(recent_items) - 1:
                ui.separator()


def attention_banner() -> None:

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
def dashboard_page():

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
                active=True,
            )

            navigation_item(
                "Inventory",
                "inventory_2",
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

        ui.label(
            "Kevin M."
        ).classes(
            "font-medium hidden md:block"
        )

        ui.button(
            icon="keyboard_arrow_down"
        ).props(
            "flat round dense color=grey-8"
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
                on_click=lambda: ui.notify(
                    "Add Item page will be implemented later."
                ),
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

            value_by_category_card()

            recent_items_card()

        # ----------------------------------------------------------
        # ATTENTION / REVIEW BANNER
        # ----------------------------------------------------------

        attention_banner()


# ------------------------------------------------------------------
# START NICEGUI
# ------------------------------------------------------------------

ui.run(
    title="CoverWorth",
    favicon="📦",
    port=8080,
    reload=True,
)