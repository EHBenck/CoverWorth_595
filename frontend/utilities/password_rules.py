"""Password hints shared by registration and Settings > Change Password."""

from nicegui import ui

# Mirrors Django's AUTH_PASSWORD_VALIDATORS in backend settings.
# Rules with a check are ticked while typing; the server confirms the rest.
PASSWORD_RULES = [
    ("At least 8 characters", lambda value: len(value) >= 8),
    ("Not only numbers", lambda value: bool(value) and not value.isdigit()),
    ("Not too similar to your name, username, or email", None),
    ("Not a commonly used password", None),
]


def show_password_rules(password: ui.input) -> None:
    """Render the rule list under `password` and tick rules as the user types."""
    rule_icons = []

    with ui.column().classes("w-full gap-1 -mt-2 px-1"):
        ui.label("Your password must be:").classes("text-xs text-grey-7")
        for text, check in PASSWORD_RULES:
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
