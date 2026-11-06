from collections.abc import Callable, Sequence
from typing import TypeVar

from nicegui import ui


T = TypeVar("T")

ui.add_css("""
    .data-table-wrapper {
        width: 100%;
        overflow-x: auto;
    }

    .data-table {
        width: 100%;
        min-width: 1000px;
    }

    .data-table-grid {
        display: grid !important;
        grid-template-columns: var(--data-table-columns) !important;
        align-items: center !important;
        width: 100%;
    }

    .data-table-header {
        min-height: 52px;
        padding: 0 12px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        color: #475569;
        font-size: 13px;
        font-weight: 600;
    }

    .data-table-header > *,
    .data-table-row > * {
        min-width: 0;
    }

    .data-table-row {
        min-height: 76px;
        padding: 0 12px;
        border-bottom: 1px solid #e2e8f0;
        transition: background-color 0.15s ease;
    }

    .data-table-row:hover {
        background: #f8fafc;
    }

    .data-table.grid-view {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 16px;
        min-width: 0;
    }

    .data-table.grid-view .data-table-header {
        display: none !important;
    }

    .data-table.grid-view .data-table-row {
        min-height: 190px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: #ffffff;
    }

    @media (max-width: 600px) {
        .data-table.grid-view {
            grid-template-columns: 1fr;
        }
    }
""", shared=True)


def add_view_mode_toggle(on_change: Callable[[], None]) -> dict[str, str]:
    view_mode = {"value": "list"}
    buttons: dict[str, ui.button] = {}

    def set_view_mode(mode: str) -> None:
        view_mode["value"] = mode
        buttons["list"].props(
            "outline color=primary"
            if mode == "list"
            else "flat color=grey-8"
        )
        buttons["grid"].props(
            "outline color=primary"
            if mode == "grid"
            else "flat color=grey-8"
        )
        on_change()

    with ui.button_group().props("flat"):
        buttons["list"] = ui.button(
            icon="view_list",
            on_click=lambda: set_view_mode("list"),
        ).props("outline color=primary").tooltip("List view")
        buttons["grid"] = ui.button(
            icon="grid_view",
            on_click=lambda: set_view_mode("grid"),
        ).props("flat color=grey-8").tooltip("Grid view")

    return view_mode


def render_data_table(
    items: Sequence[T],
    *,
    view_mode: dict[str, str],
    grid_columns: str,
    wrapper_class: str,
    table_class: str,
    header_class: str,
    row_class: str,
    render_header: Callable[[], None],
    render_row: Callable[[T], None],
    empty_icon: str,
    empty_title: str,
    empty_description: str,
    empty_padding: str = "py-16",
    render_footer: Callable[[], None] | None = None,
) -> None:
    with ui.element("div").classes(f"data-table-wrapper {wrapper_class}"):
        table_classes = f"data-table {table_class}"
        if view_mode["value"] == "grid":
            table_classes += " grid-view"

        with ui.element("div").classes(table_classes):
            with ui.element("div").classes(
                f"data-table-grid data-table-header {header_class}"
            ).style(f"--data-table-columns: {grid_columns}"):
                ui.checkbox()
                render_header()

            if not items:
                with ui.column().classes(
                    f"w-full items-center justify-center {empty_padding} gap-2"
                ):
                    ui.icon(empty_icon).classes("text-5xl text-slate-300")
                    ui.label(empty_title).classes(
                        "text-lg font-semibold text-slate-600"
                    )
                    ui.label(empty_description).classes("text-sm muted")
            else:
                for item in items:
                    with ui.element("div").classes(
                        f"data-table-grid data-table-row {row_class}"
                    ).style(f"--data-table-columns: {grid_columns}"):
                        ui.checkbox()
                        render_row(item)

    if render_footer:
        render_footer()
