import requests
from nicegui import app, run, ui

from backend_client import BACKEND_URL, authenticated_session, csrf_headers
from utilities.inventory_management import _sign_in_again, show_inventory_management
from utilities.nav_wrapper import build_app_shell
from utilities.password_rules import show_password_rules

# SETTINGS PAGE
# -----------------------------------------------------------
# TODO:
#   - Account deletion workflow
# ============================================================


# ACCOUNT API
# ============================================================
class AccountApiError(Exception):
    """An account request failed or Django rejected it."""

    def __init__(self, message: str, errors: dict | None = None):
        super().__init__(message)
        self.errors = errors or {}


class AccountSessionExpired(AccountApiError):
    """The Django login session no longer exists."""


def _account_request(
    cookies: dict,
    method: str,
    endpoint: str,
    payload: dict | None = None,
) -> tuple[dict, dict]:
    """Keep HTTP work off the UI loop and return Django's (possibly rotated) cookies."""
    with authenticated_session(cookies) as session:
        headers = csrf_headers(session) if method != "GET" else {}
        response = session.request(
            method,
            f"{BACKEND_URL}{endpoint}",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.status_code == 401:
            raise AccountSessionExpired("Your session expired. Please sign in again.")
        try:
            result = response.json()
        except ValueError:
            result = None
        if not isinstance(result, dict):
            raise AccountApiError(f"Account request failed (HTTP {response.status_code}).")
        if not response.ok:
            errors = result.get("errors")
            raise AccountApiError(
                result.get("error") or "Please check the form and try again.",
                errors if isinstance(errors, dict) else {},
            )
        return result, session.cookies.get_dict()


def _show_field_errors(fields: dict, field_errors: dict) -> None:
    for name, field in fields.items():
        messages = field_errors.get(name, [])
        field.props["error"] = bool(messages)
        field.props["error-message"] = " ".join(messages)
        field.update()


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

    account = {}
    account_load_error = ""
    try:
        result, cookies = await run.io_bound(
            _account_request,
            dict(app.storage.user.get("auth_cookies", {})),
            "GET",
            "/api/account/",
        )
    except AccountSessionExpired:
        _sign_in_again()
        return
    except (requests.RequestException, AccountApiError):
        account_load_error = "Could not load your account details. Please refresh the page."
    else:
        app.storage.user["auth_cookies"] = cookies
        account = result.get("account", {})

    loading.delete()

    username = account.get("username") or app.storage.user.get(
        "username",
        "User",
    )

    initials = username[:2].upper() if username else "CW"
    state = {"busy": False}

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

                        ui.link("Account", "#account").classes(
                            "text-sm text-inherit no-underline"
                        )

                    # SECURITY
                    # -----------------------------------------
                    with ui.row().classes("settings-nav-item " "items-center gap-3"):

                        ui.icon("lock").classes("text-xl")

                        ui.link("Security", "#security").classes(
                            "text-sm text-inherit no-underline"
                        )

            # RIGHT CONTENT
            # =================================================
            with ui.column().classes("w-full gap-5"):

                show_inventory_management()

                # ACCOUNT
                # =================================================
                with ui.card().classes("settings-card " "w-full p-6 gap-5").props(
                    "id=account"
                ):

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
                                value=account.get("first_name", ""),
                            )
                            .props("outlined autocomplete=given-name maxlength=150")
                            .classes("settings-field w-full")
                            .mark("account-first-name")
                        )

                        last_name = (
                            ui.input(
                                label="Last Name",
                                placeholder="Last name",
                                value=account.get("last_name", ""),
                            )
                            .props("outlined autocomplete=family-name maxlength=150")
                            .classes("settings-field w-full")
                            .mark("account-last-name")
                        )

                        email = (
                            ui.input(
                                label="Email",
                                placeholder="Email address",
                                value=account.get("email", ""),
                            )
                            .props("outlined type=email autocomplete=email maxlength=254")
                            .classes("settings-field w-full")
                            .mark("account-email")
                        )

                        username_input = (
                            ui.input(
                                label="Username",
                                value=username,
                            )
                            .props("outlined disable")
                            .classes("settings-field w-full")
                        )

                    account_fields = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                    }

                    account_error = (
                        ui.label(account_load_error)
                        .classes("text-sm text-negative")
                        .props("role=alert")
                    )

                    async def save_account() -> None:
                        if state["busy"]:
                            return
                        state["busy"] = True
                        account_error.text = ""
                        _show_field_errors(account_fields, {})
                        save_account_button.disable()
                        try:
                            result, cookies = await run.io_bound(
                                _account_request,
                                dict(app.storage.user.get("auth_cookies", {})),
                                "PATCH",
                                "/api/account/",
                                {
                                    name: field.value or ""
                                    for name, field in account_fields.items()
                                },
                            )
                        except AccountSessionExpired:
                            _sign_in_again()
                        except AccountApiError as error:
                            _show_field_errors(account_fields, error.errors)
                            account_error.text = str(error)
                        except requests.RequestException:
                            account_error.text = (
                                "Could not save your account. Please try again."
                            )
                        else:
                            app.storage.user["auth_cookies"] = cookies
                            # Show the trimmed values Django actually stored.
                            for name, field in account_fields.items():
                                field.value = result["account"][name]
                            ui.notify("Account updated.", type="positive")
                        finally:
                            state["busy"] = False
                            if not account_load_error:
                                save_account_button.enable()

                    with ui.row().classes("w-full justify-end"):

                        save_account_button = ui.button(
                            "Save Account",
                            icon="save",
                            on_click=save_account,
                        ).props("unelevated " "color=primary " "no-caps").classes(
                            "px-5"
                        )

                    # Saving without the stored values would overwrite them.
                    if account_load_error:
                        save_account_button.disable()

                # CHANGE PASSWORD DIALOG
                # =================================================
                with ui.dialog().props("persistent").mark(
                    "change-password-dialog"
                ) as password_dialog:
                    with ui.card().classes("w-[480px] max-w-full p-6 gap-4"):
                        ui.label("Change password").classes("text-xl font-bold")

                        current_password = (
                            ui.input("Current password", password=True)
                            .props("outlined autofocus autocomplete=current-password")
                            .classes("w-full")
                            .mark("current-password")
                        )
                        new_password = (
                            ui.input("New password", password=True)
                            .props("outlined autocomplete=new-password")
                            .classes("w-full")
                            .mark("new-password")
                        )

                        show_password_rules(new_password)

                        new_password_confirm = (
                            ui.input("Confirm new password", password=True)
                            .props("outlined autocomplete=new-password")
                            .classes("w-full")
                            .mark("new-password-confirm")
                        )
                        password_error = (
                            ui.label().classes("text-sm text-negative").props("role=alert")
                        )

                        password_fields = {
                            "current_password": current_password,
                            "new_password": new_password,
                            "new_password_confirm": new_password_confirm,
                        }

                        def reset_password_form() -> None:
                            for field in password_fields.values():
                                field.value = ""
                            _show_field_errors(password_fields, {})
                            password_error.text = ""

                        async def change_password() -> None:
                            if state["busy"]:
                                return
                            password_error.text = ""
                            _show_field_errors(password_fields, {})
                            if new_password.value != new_password_confirm.value:
                                _show_field_errors(
                                    password_fields,
                                    {"new_password_confirm": ["Passwords do not match."]},
                                )
                                return

                            state["busy"] = True
                            controls = (confirm_password, password_cancel, *password_fields.values())
                            for control in controls:
                                control.disable()
                            try:
                                _, cookies = await run.io_bound(
                                    _account_request,
                                    dict(app.storage.user.get("auth_cookies", {})),
                                    "POST",
                                    "/api/account/password/",
                                    {
                                        name: field.value or ""
                                        for name, field in password_fields.items()
                                    },
                                )
                            except AccountSessionExpired:
                                password_dialog.close()
                                _sign_in_again()
                            except AccountApiError as error:
                                _show_field_errors(password_fields, error.errors)
                                password_error.text = str(error)
                            except requests.RequestException:
                                password_error.text = (
                                    "Could not change your password. Please try again."
                                )
                            else:
                                # Django rotated the session key; keep the new cookie
                                # so this browser stays signed in.
                                app.storage.user["auth_cookies"] = cookies
                                password_dialog.close()
                                reset_password_form()
                                ui.notify("Password changed.", type="positive")
                            finally:
                                state["busy"] = False
                                for control in controls:
                                    control.enable()

                        def cancel_password_change() -> None:
                            password_dialog.close()
                            reset_password_form()

                        with ui.row().classes("w-full justify-end gap-2"):
                            password_cancel = ui.button(
                                "Cancel", on_click=cancel_password_change
                            ).props("flat no-caps").mark("cancel-password-change")
                            confirm_password = ui.button(
                                "Update password", on_click=change_password
                            ).props("unelevated no-caps color=primary")

                # SECURITY
                # =================================================
                with ui.card().classes("settings-card " "w-full p-6 gap-4").props(
                    "id=security"
                ):

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
                            on_click=password_dialog.open,
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
