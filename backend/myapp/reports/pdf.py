from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as PDFImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import AttachmentType


def build_pdf_report(
    items,
    category_name,
    *,
    include_purchase_prices,
    include_current_values,
    include_serial_numbers,
    include_photos,
    include_receipts,
):
    # Evaluate once so we can calculate totals
    # and build the PDF from the same results.
    items = list(items)

    # REPORT SUMMARY
    # ========================================================
    total_items = len(items)

    estimated_value = sum(
        (item.effective_value if item.effective_value is not None else Decimal("0.00"))
        for item in items
    )

    # CREATE PDF
    # ========================================================
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.60 * inch,
        bottomMargin=0.65 * inch,
        title="CoverWorth Inventory Report",
        author="CoverWorth",
    )

    styles = getSampleStyleSheet()

    # CUSTOM STYLES
    # ========================================================
    title_style = ParagraphStyle(
        "CoverWorthTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=0,
    )

    subtitle_style = ParagraphStyle(
        "CoverWorthSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )

    section_style = ParagraphStyle(
        "CoverWorthSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=5,
    )

    summary_style = ParagraphStyle(
        "CoverWorthSummary",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#334155"),
    )

    item_style = ParagraphStyle(
        "CoverWorthItem",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
    )

    detail_style = ParagraphStyle(
        "CoverWorthDetail",
        parent=item_style,
        textColor=colors.HexColor("#64748b"),
    )

    value_style = ParagraphStyle(
        "CoverWorthValue",
        parent=item_style,
        fontName="Helvetica-Bold",
        alignment=2,
    )

    story = []

    # HEADER
    # ========================================================
    logo_text = Paragraph(
        "<b>CW</b>",
        ParagraphStyle(
            "LogoText",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            alignment=1,
            textColor=colors.HexColor("#2563eb"),
        ),
    )

    brand_text = Paragraph(
        (
            "<b>CoverWorth</b><br/>"
            '<font size="9" color="#64748b">'
            "Inventory Report"
            "</font>"
        ),
        title_style,
    )

    header_table = Table(
        [
            [
                logo_text,
                brand_text,
            ]
        ],
        colWidths=[
            0.55 * inch,
            5.8 * inch,
        ],
    )

    header_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    colors.HexColor("#eff6ff"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (0, 0),
                    0.5,
                    colors.HexColor("#dbeafe"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (0, 0),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (0, 0),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (0, 0),
                    10,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (0, 0),
                    10,
                ),
                (
                    "LEFTPADDING",
                    (1, 0),
                    (1, 0),
                    12,
                ),
            ]
        )
    )

    story.append(header_table)

    story.append(
        Spacer(
            1,
            16,
        )
    )

    # Thin divider like the preview.
    divider = Table(
        [[""]],
        colWidths=[6.9 * inch],
        rowHeights=[1],
    )

    divider.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#e2e8f0"),
                ),
            ]
        )
    )

    story.append(divider)

    story.append(
        Spacer(
            1,
            16,
        )
    )

    # SUMMARY
    # ========================================================
    story.append(
        Paragraph(
            "Inventory Summary",
            section_style,
        )
    )

    story.append(
        Paragraph(
            f"{total_items:,} items",
            summary_style,
        )
    )

    story.append(
        Paragraph(
            ("Estimated value: " f"${estimated_value:,.2f}"),
            summary_style,
        )
    )

    if category_name:

        story.append(
            Paragraph(
                ("Category: " f"{escape(category_name)}"),
                summary_style,
            )
        )

    story.append(
        Spacer(
            1,
            14,
        )
    )

    # ITEM TABLE
    # ========================================================
    table_rows = [
        [
            Paragraph(
                "<b>Item</b>",
                item_style,
            ),
            Paragraph(
                "<b>Value</b>",
                value_style,
            ),
        ]
    ]

    for item in items:

        item_details = []

        # Category
        category_text = item.category.name if item.category else "Uncategorized"

        item_details.append(
            ('<font color="#64748b">' f"{escape(category_text)}" "</font>")
        )

        # Location
        if item.location:

            item_details.append(
                (
                    '<font color="#64748b">'
                    f"Location: "
                    f"{escape(item.location.name)}"
                    "</font>"
                )
            )

        # Serial / model
        if include_serial_numbers:

            if item.model_number:

                item_details.append(
                    (
                        '<font color="#64748b">'
                        "Model: "
                        f"{escape(item.model_number)}"
                        "</font>"
                    )
                )

            if item.serial_number:

                item_details.append(
                    (
                        '<font color="#64748b">'
                        "Serial: "
                        f"{escape(item.serial_number)}"
                        "</font>"
                    )
                )

        # Purchase information
        if include_purchase_prices:

            purchase_parts = []

            if item.purchase_date:

                purchase_parts.append(
                    item.purchase_date.strftime("%b %d, %Y").replace(
                        " 0",
                        " ",
                    )
                )

            if item.purchase_amount is not None:

                purchase_parts.append(f"${item.purchase_amount:,.2f}")

            if purchase_parts:

                item_details.append(
                    (
                        '<font color="#64748b">'
                        "Purchased: "
                        f"{escape(' • '.join(purchase_parts))}"
                        "</font>"
                    )
                )

        # ATTACHMENTS
        # ----------------------------------------------------
        attachments = [
            attachment
            for attachment in item.attachments.all()
            if attachment.archived_at is None
        ]

        photo_attachment = None

        if include_photos:

            photos = [
                attachment
                for attachment in attachments
                if (attachment.file_type == AttachmentType.PHOTO)
            ]

            if photos:

                photos.sort(
                    key=lambda attachment: (
                        attachment.is_primary,
                        attachment.uploaded_at,
                    ),
                    reverse=True,
                )

                photo_attachment = photos[0]

        if include_receipts:

            supporting_documents = [
                attachment
                for attachment in attachments
                if (attachment.file_type != AttachmentType.PHOTO)
            ]

            if supporting_documents:

                document_names = [
                    (attachment.original_filename or attachment.get_file_type_display())
                    for attachment in supporting_documents[:3]
                ]

                if len(supporting_documents) > 3:

                    document_names.append(
                        (f"+" f"{len(supporting_documents) - 3}" " more")
                    )

                item_details.append(
                    (
                        '<font color="#64748b">'
                        "Documents: "
                        f"{escape(', '.join(document_names))}"
                        "</font>"
                    )
                )

        # ITEM TEXT
        # ----------------------------------------------------
        item_text = Paragraph(
            (f"<b>{escape(item.name)}</b>" "<br/>" + "<br/>".join(item_details)),
            item_style,
        )

        item_cell = item_text

        # OPTIONAL PRIMARY PHOTO
        # ----------------------------------------------------
        if photo_attachment and photo_attachment.file:

            try:

                photo_attachment.file.open("rb")

                photo_bytes = photo_attachment.file.read()

                photo_attachment.file.close()

                photo = PDFImage(
                    BytesIO(photo_bytes),
                    width=0.55 * inch,
                    height=0.55 * inch,
                )

                item_cell = Table(
                    [
                        [
                            photo,
                            item_text,
                        ]
                    ],
                    colWidths=[
                        0.70 * inch,
                        4.75 * inch,
                    ],
                )

                item_cell.setStyle(
                    TableStyle(
                        [
                            (
                                "VALIGN",
                                (0, 0),
                                (-1, -1),
                                "TOP",
                            ),
                            (
                                "LEFTPADDING",
                                (0, 0),
                                (-1, -1),
                                0,
                            ),
                            (
                                "RIGHTPADDING",
                                (0, 0),
                                (-1, -1),
                                6,
                            ),
                            (
                                "TOPPADDING",
                                (0, 0),
                                (-1, -1),
                                0,
                            ),
                            (
                                "BOTTOMPADDING",
                                (0, 0),
                                (-1, -1),
                                0,
                            ),
                        ]
                    )
                )

            except (
                OSError,
                ValueError,
            ):

                # If the photo cannot be read,
                # simply render the text.
                item_cell = item_text

        # VALUE
        # ----------------------------------------------------
        if include_current_values and item.effective_value is not None:

            value_text = f"${item.effective_value:,.2f}"

        else:

            value_text = "—"

        table_rows.append(
            [
                item_cell,
                Paragraph(
                    value_text,
                    value_style,
                ),
            ]
        )

    # Empty inventory/category
    if not items:

        table_rows.append(
            [
                Paragraph(
                    ("No items matched " "this report."),
                    detail_style,
                ),
                "",
            ]
        )

    item_table = Table(
        table_rows,
        colWidths=[
            5.65 * inch,
            1.15 * inch,
        ],
        repeatRows=1,
    )

    item_table.setStyle(
        TableStyle(
            [
                # Header
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#f1f5f9"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#0f172a"),
                ),
                # All cells
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                # Row separators
                (
                    "LINEBELOW",
                    (0, 1),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#e2e8f0"),
                ),
            ]
        )
    )

    story.append(item_table)

    # FOOTER
    # ========================================================
    def draw_footer(
        canvas,
        doc,
    ):

        canvas.saveState()

        canvas.setFont(
            "Helvetica",
            8,
        )

        canvas.setFillColor(colors.HexColor("#94a3b8"))

        canvas.drawCentredString(
            letter[0] / 2,
            0.35 * inch,
            "Generated by CoverWorth",
        )

        canvas.restoreState()

    # BUILD
    # ========================================================
    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    pdf_data = buffer.getvalue()

    buffer.close()

    return pdf_data
