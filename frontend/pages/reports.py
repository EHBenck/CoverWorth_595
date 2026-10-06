import requests

from nicegui import app, ui

from backend_client import BACKEND_URL, authenticated_session
from utilities.nav_wrapper import build_app_shell


# ============================================================
# COVERWORTH - REPORTS PAGE
# ------------------------------------------------------------
# TODO:
#   - Add Django report generation endpoints
#   - Download generated PDF / CSV reports
#   - Populate collections dynamically
# ============================================================


# ============================================================
# STYLING
# ============================================================

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


    /* ========================================================
       REPORT PAGE
       ======================================================== */

    .reports-container {
        width: 100%;
    }

    .muted {
        color: #64748b;
    }

    .reports-card {
        background: #ffffff;
        border: 1px solid #e1e7ef;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }


    /* ========================================================
       SUMMARY
       ======================================================== */

    .summary-panel {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
    }

    .summary-value {
        font-size: 30px;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.1;
    }

    .summary-label {
        font-size: 13px;
        color: #64748b;
    }

    .summary-icon {
        width: 52px;
        height: 52px;
        border-radius: 12px;
        background: #eff6ff;

        display: flex;
        align-items: center;
        justify-content: center;
    }


    /* ========================================================
       REPORT OPTIONS
       ======================================================== */

    .report-section-title {
        font-size: 16px;
        font-weight: 700;
        color: #0f172a;
    }

    .option-row {
        width: 100%;
        min-height: 46px;
        border-radius: 8px;
        padding: 4px 8px;
    }

    .option-row:hover {
        background: #f8fafc;
    }

    .filter-control .q-field__control {
        min-height: 46px;
    }


    /* ========================================================
       FORMAT CARDS
       ======================================================== */

    .format-card {
        border: 1px solid #dbe3ec;
        border-radius: 10px;
        padding: 16px;
        cursor: pointer;
        transition:
            border-color 0.15s ease,
            background-color 0.15s ease;
    }

    .format-card:hover {
        background: #f8fafc;
    }

    .format-icon {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        background: #f1f5f9;

        display: flex;
        align-items: center;
        justify-content: center;
    }


    /* ========================================================
       REPORT PREVIEW
       ======================================================== */

    .report-preview {
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 10px;
    }

    .preview-document {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(15, 23, 42, 0.04);
    }

    .preview-line {
        height: 7px;
        background: #e2e8f0;
        border-radius: 999px;
    }


    /* ========================================================
       RESPONSIVE
       ======================================================== */

    @media (max-width: 1000px) {
        .reports-layout {
            grid-template-columns: 1fr !important;
        }
    }
""", shared=True)


# ============================================================
# DATA
# ============================================================

def load_report_summary() -> dict:
    """
    Use the existing dashboard endpoint so Reports can display
    real inventory totals without requiring a new backend route.
    """

    default_summary = {
        "total_items": 0,
        "estimated_value": 0,
        "purchase_value": 0,
        "items_needing_attention": 0,
    }

    cookies = app.storage.user.get("auth_cookies")

    if not cookies:
        return default_summary

    try:
        response = authenticated_session(cookies).get(
            f"{BACKEND_URL}/api/dashboard/",
            timeout=5,
        )

        if response.status_code == 401:
            return default_summary

        response.raise_for_status()

        data = response.json()

        return data.get(
            "summary",
            default_summary,
        )

    except requests.RequestException as error:
        print(f"Error loading report summary: {error}")
        return default_summary


# ============================================================
# REPORTS PAGE
# ============================================================

@ui.page("/reports")
def reports_page():

    ui.page_title(
        "Reports | CoverWorth"
    )

    build_app_shell(
        "Reports",
        username=app.storage.user.get(
            "username",
            "User",
        ),
    )

    summary = load_report_summary()


    # ========================================================
    # PAGE CONTENT
    # ========================================================

    with ui.column().classes(
        "reports-container "
        "page-content-frame "
        "p-7 gap-6"
    ):


        # ----------------------------------------------------
        # PAGE HEADER
        # ----------------------------------------------------

        with ui.column().classes(
            "gap-0"
        ):

            ui.label(
                "Reports"
            ).classes(
                "text-4xl "
                "font-bold "
                "tracking-tight"
            )

            ui.label(
                "Create a record of your belongings and their value."
            ).classes(
                "text-base muted"
            )


        # ====================================================
        # MAIN REPORT LAYOUT
        # ====================================================

        with ui.grid().classes(
            "reports-layout "
            "w-full "
            "grid-cols-[1.15fr_0.85fr] "
            "gap-5"
        ):


            # =================================================
            # LEFT SIDE - REPORT OPTIONS
            # =================================================

            with ui.card().classes(
                "reports-card "
                "w-full "
                "p-6 gap-6"
            ):


                # ---------------------------------------------
                # INVENTORY SUMMARY
                # ---------------------------------------------

                with ui.column().classes(
                    "w-full gap-3"
                ):

                    ui.label(
                        "Inventory Summary"
                    ).classes(
                        "text-xl font-bold"
                    )

                    ui.label(
                        "The current totals that will be used "
                        "in your report."
                    ).classes(
                        "text-sm muted"
                    )


                    # Item count
                    with ui.row().classes(
                        "summary-panel "
                        "w-full "
                        "items-center "
                        "justify-between "
                        "p-4"
                    ):

                        with ui.row().classes(
                            "items-center gap-4"
                        ):

                            with ui.element(
                                "div"
                            ).classes(
                                "summary-icon"
                            ):

                                ui.icon(
                                    "inventory_2"
                                ).classes(
                                    "text-2xl "
                                    "text-blue-600"
                                )

                            with ui.column().classes(
                                "gap-0"
                            ):

                                ui.label(
                                    f'{summary["total_items"]:,}'
                                ).classes(
                                    "summary-value"
                                )

                                ui.label(
                                    "Items"
                                ).classes(
                                    "summary-label"
                                )


                    # Estimated value
                    with ui.row().classes(
                        "summary-panel "
                        "w-full "
                        "items-center "
                        "justify-between "
                        "p-4"
                    ):

                        with ui.row().classes(
                            "items-center gap-4"
                        ):

                            with ui.element(
                                "div"
                            ).classes(
                                "summary-icon"
                            ):

                                ui.icon(
                                    "paid"
                                ).classes(
                                    "text-2xl "
                                    "text-green-600"
                                )

                            with ui.column().classes(
                                "gap-0"
                            ):

                                ui.label(
                                    f'${summary["estimated_value"]:,.0f}'
                                ).classes(
                                    "summary-value"
                                )

                                ui.label(
                                    "Estimated Replacement Value"
                                ).classes(
                                    "summary-label"
                                )


                ui.separator()


                # ---------------------------------------------
                # INCLUDE OPTIONS
                # ---------------------------------------------

                with ui.column().classes(
                    "w-full gap-2"
                ):

                    ui.label(
                        "Include"
                    ).classes(
                        "report-section-title"
                    )

                    ui.label(
                        "Choose the information that should "
                        "appear in the report."
                    ).classes(
                        "text-sm muted mb-1"
                    )


                    include_photos = ui.checkbox(
                        "Item photos",
                        value=True,
                    )

                    include_purchase_prices = ui.checkbox(
                        "Purchase prices",
                        value=True,
                    )

                    include_current_values = ui.checkbox(
                        "Current valuations",
                        value=True,
                    )

                    include_serial_numbers = ui.checkbox(
                        "Serial and model numbers",
                        value=True,
                    )

                    include_receipts = ui.checkbox(
                        "Receipts and supporting documents",
                        value=True,
                    )


                ui.separator()


                # ---------------------------------------------
                # FILTERS
                # ---------------------------------------------

                with ui.column().classes(
                    "w-full gap-3"
                ):

                    ui.label(
                        "Filter"
                    ).classes(
                        "report-section-title"
                    )

                    ui.label(
                        "Limit the report to a specific collection."
                    ).classes(
                        "text-sm muted"
                    )

                    collection_filter = ui.select(
                        [
                            "All Collections",
                            "Electronics",
                            "Watches",
                            "Collectibles",
                            "Furniture",
                        ],
                        value="All Collections",
                        label="Collection",
                    ).props(
                        "outlined"
                    ).classes(
                        "filter-control w-full"
                    )


                ui.separator()


                # ---------------------------------------------
                # REPORT FORMAT
                # ---------------------------------------------

                with ui.column().classes(
                    "w-full gap-3"
                ):

                    ui.label(
                        "Report Format"
                    ).classes(
                        "report-section-title"
                    )

                    ui.label(
                        "Choose how you want the report exported."
                    ).classes(
                        "text-sm muted"
                    )


                    report_format = ui.radio(
                        {
                            "PDF": "PDF",
                            "CSV": "CSV",
                        },
                        value="PDF",
                    ).props(
                        "inline"
                    )


                    # PDF description
                    with ui.row().classes(
                        "format-card "
                        "w-full "
                        "items-center "
                        "gap-4"
                    ).on(
                        "click",
                        lambda: report_format.set_value("PDF"),
                    ):

                        with ui.element(
                            "div"
                        ).classes(
                            "format-icon"
                        ):

                            ui.icon(
                                "picture_as_pdf"
                            ).classes(
                                "text-2xl text-red-600"
                            )

                        with ui.column().classes(
                            "gap-0"
                        ):

                            ui.label(
                                "PDF Report"
                            ).classes(
                                "font-semibold"
                            )

                            ui.label(
                                "Formatted document suitable "
                                "for insurance or record keeping."
                            ).classes(
                                "text-sm muted"
                            )


                    # CSV description
                    with ui.row().classes(
                        "format-card "
                        "w-full "
                        "items-center "
                        "gap-4"
                    ).on(
                        "click",
                        lambda: report_format.set_value("CSV"),
                    ):

                        with ui.element(
                            "div"
                        ).classes(
                            "format-icon"
                        ):

                            ui.icon(
                                "table_view"
                            ).classes(
                                "text-2xl text-green-700"
                            )

                        with ui.column().classes(
                            "gap-0"
                        ):

                            ui.label(
                                "CSV Spreadsheet"
                            ).classes(
                                "font-semibold"
                            )

                            ui.label(
                                "Raw inventory data for use "
                                "in Excel or another spreadsheet."
                            ).classes(
                                "text-sm muted"
                            )


                # ---------------------------------------------
                # GENERATE BUTTON
                # ---------------------------------------------

                def generate_report():

                    selected_options = []

                    if include_photos.value:
                        selected_options.append("photos")

                    if include_purchase_prices.value:
                        selected_options.append(
                            "purchase prices"
                        )

                    if include_current_values.value:
                        selected_options.append(
                            "current valuations"
                        )

                    if include_serial_numbers.value:
                        selected_options.append(
                            "serial numbers"
                        )

                    if include_receipts.value:
                        selected_options.append(
                            "receipts"
                        )

                    ui.notify(
                        (
                            f"{report_format.value} report ready "
                            f"to generate for "
                            f"{collection_filter.value}."
                        ),
                        type="positive",
                    )


                with ui.row().classes(
                    "w-full justify-end pt-2"
                ):

                    ui.button(
                        "Generate Report",
                        icon="description",
                        on_click=generate_report,
                    ).props(
                        "unelevated "
                        "color=primary "
                        "no-caps"
                    ).classes(
                        "px-6 py-2 rounded-lg"
                    )


            # =================================================
            # RIGHT SIDE - REPORT PREVIEW
            # =================================================

            with ui.card().classes(
                "reports-card "
                "w-full "
                "p-6 gap-5"
            ):

                with ui.column().classes(
                    "gap-0"
                ):

                    ui.label(
                        "Report Preview"
                    ).classes(
                        "text-xl font-bold"
                    )

                    ui.label(
                        "Example layout of the generated report."
                    ).classes(
                        "text-sm muted"
                    )


                # ---------------------------------------------
                # PREVIEW AREA
                # ---------------------------------------------

                with ui.column().classes(
                    "report-preview "
                    "w-full "
                    "items-center "
                    "p-6"
                ):


                    # Mock document
                    with ui.column().classes(
                        "preview-document "
                        "w-full "
                        "max-w-[430px] "
                        "p-6 gap-4"
                    ):


                        # Document heading
                        with ui.row().classes(
                            "w-full "
                            "items-center "
                            "gap-3"
                        ):

                            with ui.element(
                                "div"
                            ).classes(
                                "w-10 h-10 "
                                "rounded-lg "
                                "bg-blue-50 "
                                "flex "
                                "items-center "
                                "justify-center"
                            ):

                                ui.icon(
                                    "inventory_2"
                                ).classes(
                                    "text-xl "
                                    "text-blue-600"
                                )

                            with ui.column().classes(
                                "gap-0"
                            ):

                                ui.label(
                                    "CoverWorth"
                                ).classes(
                                    "text-lg font-bold"
                                )

                                ui.label(
                                    "Inventory Report"
                                ).classes(
                                    "text-xs muted"
                                )


                        ui.separator()


                        # Summary
                        with ui.column().classes(
                            "w-full gap-1"
                        ):

                            ui.label(
                                "Inventory Summary"
                            ).classes(
                                "text-sm font-bold"
                            )

                            ui.label(
                                f'{summary["total_items"]:,} items'
                            ).classes(
                                "text-xs text-slate-600"
                            )

                            ui.label(
                                (
                                    "Estimated value: "
                                    f'${summary["estimated_value"]:,.0f}'
                                )
                            ).classes(
                                "text-xs text-slate-600"
                            )


                        # Fake table header
                        with ui.row().classes(
                            "w-full "
                            "items-center "
                            "justify-between "
                            "bg-slate-100 "
                            "rounded-md "
                            "px-3 py-2"
                        ):

                            ui.label(
                                "Item"
                            ).classes(
                                "text-xs font-semibold"
                            )

                            ui.label(
                                "Value"
                            ).classes(
                                "text-xs font-semibold"
                            )


                        # Fake document rows
                        for width in (
                            "82%",
                            "68%",
                            "76%",
                            "60%",
                            "88%",
                        ):

                            with ui.row().classes(
                                "w-full "
                                "items-center "
                                "justify-between "
                                "gap-4"
                            ):

                                ui.element(
                                    "div"
                                ).classes(
                                    "preview-line"
                                ).style(
                                    f"width: {width};"
                                )

                                ui.element(
                                    "div"
                                ).classes(
                                    "preview-line "
                                    "w-[55px]"
                                )


                        ui.separator()


                        # Footer
                        ui.label(
                            "Generated by CoverWorth"
                        ).classes(
                            "text-[10px] "
                            "text-slate-400 "
                            "self-center"
                        )


                # ---------------------------------------------
                # REPORT PURPOSE NOTE
                # ---------------------------------------------

                with ui.row().classes(
                    "w-full "
                    "items-start "
                    "gap-3 "
                    "bg-blue-50 "
                    "rounded-lg "
                    "p-4"
                ):

                    ui.icon(
                        "info"
                    ).classes(
                        "text-xl text-blue-600"
                    )

                    with ui.column().classes(
                        "gap-0"
                    ):

                        ui.label(
                            "Keep a current record"
                        ).classes(
                            "text-sm "
                            "font-semibold "
                            "text-blue-900"
                        )

                        ui.label(
                            "Reports can provide a snapshot "
                            "of your belongings, purchase "
                            "information, and current values."
                        ).classes(
                            "text-xs text-blue-800"
                        )