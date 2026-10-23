import requests
from nicegui import app, ui
from backend_client import BACKEND_URL, csrf_headers


# COVERWORTH - REGISTER PAGE
# ------------------------------------------------------------
# Creates a Django account and signs the new user in.


# REGISTER PAGE
@ui.page("/register")
def register_page():

    if app.storage.user.get("auth_cookies"):
        ui.navigate.to("/dashboard")
        return

    ui.page_title("Register | CoverWorth")

    with ui.column().classes("w-full min-h-screen items-center justify-center p-6"):
        with ui.card().classes("w-full max-w-md p-8 gap-5"):
            ui.label("CoverWorth").classes("text-3xl font-bold text-primary")
            ui.label("Create your account").classes("text-lg")

            with ui.row().classes("w-full gap-4 no-wrap"):
                first_name = ui.input("First name").props(
                    "outlined autocomplete=given-name"
                ).classes("flex-1")
                last_name = ui.input("Last name").props(
                    "outlined autocomplete=family-name"
                ).classes("flex-1")

            email = ui.input("Email").props(
                "outlined type=email autocomplete=email"
            ).classes("w-full")
            username = ui.input("Username").props(
                "outlined autocomplete=username"
            ).classes("w-full")
            password = ui.input("Password", password=True).props(
                "outlined autocomplete=new-password"
            ).classes("w-full")

            # Mirrors Django's AUTH_PASSWORD_VALIDATORS in backend settings.
            # Rules with a check are ticked while typing; the server confirms the rest.
            password_rules = [
                ("At least 8 characters", lambda value: len(value) >= 8),
                ("Not only numbers", lambda value: bool(value) and not value.isdigit()),
                ("Not too similar to your name, username, or email", None),
                ("Not a commonly used password", None),
            ]
            rule_icons = []

            with ui.column().classes("w-full gap-1 -mt-2 px-1"):
                ui.label("Your password must be:").classes("text-xs text-grey-7")
                for text, check in password_rules:
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        icon = ui.icon(
                            "radio_button_unchecked" if check else "info_outline"
                        ).classes("text-sm text-grey-6")
                        ui.label(text).classes("text-xs text-grey-7")
                    if check:
                        rule_icons.append((icon, check))

            def update_password_rules(event):
                value = event.value or ""
                for icon, check in rule_icons:
                    passed = check(value)
                    icon.name = "check_circle" if passed else "radio_button_unchecked"
                    icon.classes(
                        add="text-positive" if passed else "text-grey-6",
                        remove="text-grey-6" if passed else "text-positive",
                    )

            password.on_value_change(update_password_rules)

            password_confirm = ui.input("Confirm password", password=True).props(
                "outlined autocomplete=new-password"
            ).classes("w-full")
            error = ui.label().classes("text-negative")

            fields = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "username": username,
                "password": password,
                "password_confirm": password_confirm,
            }

            def show_field_errors(field_errors):
                for name, field in fields.items():
                    messages = field_errors.get(name, [])
                    field.props["error"] = bool(messages)
                    field.props["error-message"] = " ".join(messages)
                    field.update()

            async def submit_register():
                error.text = ""

                if password.value != password_confirm.value:
                    show_field_errors({"password_confirm": ["Passwords do not match."]})
                    return

                session = requests.Session()
                try:
                    response = session.post(
                        f"{BACKEND_URL}/api/auth/register/",
                        json={name: field.value for name, field in fields.items()},
                        headers=csrf_headers(session),
                        timeout=5,
                    )
                    if response.status_code == 400:
                        data = response.json()
                        show_field_errors(data.get("errors", {}))
                        error.text = data.get("error", "Please check the form and try again.")
                        return
                    response.raise_for_status()
                except requests.RequestException:
                    error.text = "Could not connect to the server. Try again."
                    return

                app.storage.user["auth_cookies"] = session.cookies.get_dict()
                app.storage.user["username"] = response.json()["username"]
                ui.notify("Account created. Welcome to CoverWorth!", type="positive")
                ui.navigate.to("/dashboard")

            ui.button("Create account", on_click=submit_register, icon="person_add").props(
                "unelevated color=primary no-caps"
            ).classes("w-full")

            with ui.row().classes("w-full items-center justify-center gap-1"):
                ui.label("Already have an account?").classes("text-sm text-grey-7")
                ui.button("Sign in", on_click=lambda: ui.navigate.to("/")).props(
                    "flat dense color=primary no-caps"
                )
