from nicegui import app, ui
from utilities.inventory_management import show_inventory_management
from utilities.nav_wrapper import build_app_shell

# SETTINGS PAGE
# -----------------------------------------------------------
# TODO:
#   - User profile endpoint
#   - Password change endpoint
#   - Account deletion workflow
# ============================================================


# STYLING
# ============================================================
ui.add_css(
    """
    body {
        background: #f3f8fb;
        color: #0f172a;
        font-family: Inter, Roboto, Arial, sans-serif;
    }

    .nicegui-content {
        padding: 0 !important;
        background-color: #f3f8fb !important;
    }


    /* ========================================================
       PAGE
       ======================================================== */

    .settings-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }

    .settings-layout {
        display: grid;

        grid-template-columns:
            230px minmax(0, 1fr);

        width: 100%;

        gap: 24px;

        align-items: start;
    }


    /* ========================================================
       SETTINGS NAVIGATION
       ======================================================== */

    .settings-sidebar-card {
        background: #ffffff;

        border: 1px solid #e1e7ef;
        border-radius: 12px;

        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);

        overflow: hidden;
    }

    .settings-nav-item {
        width: 100%;

        min-height: 48px;

        padding: 0 14px;

        border-radius: 8px;

        color: #475569;

        cursor: pointer;

        transition:
            background-color 0.15s ease,
            color 0.15s ease;
    }

    .settings-nav-item:hover {
        background: #f8fafc;
        color: #0f172a;
    }

    .settings-nav-active {
        background: #eff6ff;
        color: #1769c2;

        font-weight: 600;
    }


    /* ========================================================
       CONTENT CARDS
       ======================================================== */

    .settings-card {
        width: 100%;

        background: #ffffff;

        border: 1px solid #e1e7ef;
        border-radius: 12px;

        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .settings-section-title {
        color: #0f172a;

        font-size: 19px;
        font-weight: 700;
    }

    .settings-field .q-field__control {
        min-height: 48px;
    }


    /* ========================================================
       PROFILE
       ======================================================== */

    .profile-avatar {
        width: 72px;
        height: 72px;

        border-radius: 50%;

        background: #1769c2;
        color: #ffffff;

        display: flex;
        align-items: center;
        justify-content: center;

        font-size: 23px;
        font-weight: 700;
    }


    /* ========================================================
       SECURITY
       ======================================================== */

    .security-row {
        width: 100%;

        min-height: 72px;

        padding: 12px 0;

        border-bottom: 1px solid #edf2f7;
    }

    .security-row:last-child {
        border-bottom: none;
    }

    .security-icon {
        width: 42px;
        height: 42px;

        border-radius: 10px;

        background: #f1f5f9;

        display: flex;
        align-items: center;
        justify-content: center;

        flex-shrink: 0;
    }

    .delete-account-row {
        width: 100%;

        margin-top: 8px;
        padding: 18px;

        background: #fffafa;

        border: 1px solid #fecaca;
        border-radius: 10px;
    }


    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 900px) {

        .settings-layout {
            grid-template-columns: 1fr;
        }

        .settings-sidebar-card {
            width: 100%;
        }

        .settings-nav-list {
            flex-direction: row !important;
            overflow-x: auto;
        }

        .settings-nav-item {
            min-width: max-content;
        }
    }
    """,
    shared=True,
)


# SETTINGS PAGE
# ============================================================
@ui.page("/settings")
async def settings_page():
    # AUTHENTICATION GUARD
    # ========================================================
    if not app.storage.user.get("auth_cookies"):
        ui.navigate.to("/")
        return

    ui.page_title("Settings | CoverWorth")

    # SHARED APP SHELL
    # =======================================================
    build_app_shell(
        "Settings",
        username=app.storage.user.get(
            "username",
            "User",
        ),
    )

    with ui.column().classes(
        "settings-container page-content-frame " "items-center justify-center gap-3 p-8"
    ) as loading:
        ui.spinner(size="lg")
        ui.label("Loading settings...").classes("muted")

    await ui.context.client.connected()
    loading.delete()

    username = app.storage.user.get(
        "username",
        "User",
    )

    initials = username[:2].upper() if username else "CW"

    # MAIN CONTENT
    # ========================================================
    with ui.column().classes("settings-container " "page-content-frame " "p-7 gap-6"):

        # PAGE HEADER
        # ====================================================
        with ui.column().classes("gap-0"):

            ui.label("Settings").classes("text-4xl " "font-bold " "tracking-tight")

            ui.label("Manage your inventories, account, and security.").classes(
                "text-base muted"
            )

        # SETTINGS LAYOUT
        # ====================================================
        with ui.element("div").classes("settings-layout"):

            # LEFT SETTINGS NAV
            # =================================================
            with ui.card().classes("settings-sidebar-card " "w-full " "p-3 gap-1"):

                with ui.column().classes("settings-nav-list " "w-full gap-1"):

                    # INVENTORIES
                    # -----------------------------------------
                    with ui.row().classes(
                        "settings-nav-item settings-nav-active items-center gap-3"
                    ):
                        ui.icon("inventory_2").classes("text-xl")
                        ui.link("Inventories", "#inventories").classes(
                            "text-sm text-inherit no-underline"
                        )

                    # ACCOUNT
                    # -----------------------------------------
                    with ui.row().classes(
                        "settings-nav-item " "items-center gap-3"
                    ):

                        ui.icon("person").classes("text-xl")

                        ui.label("Account").classes("text-sm")

                    # SECURITY
                    # -----------------------------------------
                    with ui.row().classes("settings-nav-item " "items-center gap-3"):

                        ui.icon("lock").classes("text-xl")

                        ui.label("Security").classes("text-sm")

            # RIGHT CONTENT
            # =================================================
            with ui.column().classes("w-full gap-5"):

                show_inventory_management()

                # ACCOUNT
                # =================================================
                with ui.card().classes("settings-card " "w-full p-6 gap-5"):

                    with ui.column().classes("gap-0"):

                        ui.label("Account").classes("settings-section-title")

                        ui.label(
                            ("Manage your personal " "account information.")
                        ).classes("text-sm muted")

                    # PROFILE SUMMARY
                    # -----------------------------------------
                    with ui.row().classes("w-full " "items-center " "gap-5"):

                        with ui.element("div").classes("profile-avatar"):

                            ui.label(initials)

                        with ui.column().classes("gap-1"):

                            ui.label(username).classes("text-lg " "font-semibold")

                            ui.label("CoverWorth account").classes("text-sm muted")

                    ui.separator()

                    # ACCOUNT FIELDS
                    # -----------------------------------------
                    with ui.grid(columns=2).classes(
                        "w-full gap-4 " "max-sm:grid-cols-1"
                    ):

                        first_name = (
                            ui.input(
                                label="First Name",
                                placeholder="First name",
                            )
                            .props("outlined")
                            .classes("settings-field w-full")
                        )

                        last_name = (
                            ui.input(
                                label="Last Name",
                                placeholder="Last name",
                            )
                            .props("outlined")
                            .classes("settings-field w-full")
                        )

                        email = (
                            ui.input(
                                label="Email",
                                placeholder="Email address",
                            )
                            .props("outlined type=email")
                            .classes("settings-field w-full")
                        )

                        username_input = (
                            ui.input(
                                label="Username",
                                value=username,
                            )
                            .props("outlined disable")
                            .classes("settings-field w-full")
                        )

                    ui.label(
                        ("Profile editing is not connected " "to the backend yet.")
                    ).classes("text-xs muted")

                    with ui.row().classes("w-full justify-end"):

                        ui.button(
                            "Save Account",
                            icon="save",
                            on_click=lambda: ui.notify(
                                (
                                    "Account editing will be "
                                    "connected in a future story."
                                ),
                                type="info",
                            ),
                        ).props("unelevated " "color=primary " "no-caps").classes(
                            "px-5"
                        )

                # SECURITY
                # =================================================
                with ui.card().classes("settings-card " "w-full p-6 gap-4"):

                    with ui.column().classes("gap-0"):

                        ui.label("Security").classes("settings-section-title")

                        ui.label(
                            ("Manage your password " "and account security.")
                        ).classes("text-sm muted")

                    # PASSWORD
                    # -----------------------------------------
                    with ui.row().classes(
                        "security-row " "items-center " "justify-between " "gap-4"
                    ):

                        with ui.row().classes("items-center gap-4"):

                            with ui.element("div").classes("security-icon"):

                                ui.icon("password").classes("text-xl " "text-slate-600")

                            with ui.column().classes("gap-0"):

                                ui.label("Password").classes("font-semibold")

                                ui.label(
                                    ("Change the password " "used to sign in.")
                                ).classes("text-sm muted")

                        ui.button(
                            "Change Password",
                            on_click=lambda: ui.notify(
                                ("Password management " "is not connected yet."),
                                type="info",
                            ),
                        ).props("outline " "color=primary " "no-caps")

                    # DELETE ACCOUNT
                    # -----------------------------------------
                    with ui.row().classes(
                        "delete-account-row " "items-center " "justify-between " "gap-4"
                    ):

                        with ui.row().classes("items-center gap-4"):

                            with ui.element("div").classes("security-icon"):

                                ui.icon("delete_forever").classes(
                                    "text-xl " "text-red-600"
                                )

                            with ui.column().classes("gap-0"):

                                ui.label("Delete Account").classes(
                                    "font-semibold " "text-red-700"
                                )

                                ui.label(
                                    (
                                        "Permanently remove "
                                        "your CoverWorth account "
                                        "and all associated data."
                                    )
                                ).classes("text-sm muted")

                        ui.button(
                            "Delete Account",
                            icon="delete_forever",
                            on_click=lambda: ui.notify(
                                ("Account deletion is " "not implemented yet."),
                                type="warning",
                            ),
                        ).props("outline " "color=negative " "no-caps")
