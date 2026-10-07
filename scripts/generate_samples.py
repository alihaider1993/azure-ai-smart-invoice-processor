# Generates the fictional sample invoices in samples/ used by the public demo.
# Author: Syed Ali Haider
# Run from the repo root: python scripts/generate_samples.py
#
# Each sample is designed to exercise a different path through the agents:
#   northwind_office_supplies.pdf     GBP, complete details        -> low risk, auto-approved
#   atlas_cloud_services_usd.pdf      USD, converts to > £1,000    -> manager approval
#   quickfix_maintenance_receipt.png  EUR, high-value round amount, weekend,
#                                     no invoice/VAT number        -> high fraud risk

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def build_pdf_invoice(file_name: str, invoice: dict):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(SAMPLES_DIR / file_name), pagesize=A4)
    symbol = invoice["symbol"]

    header = Table(
        [[Paragraph(f"<b>{invoice['vendor']}</b><br/>{invoice['vendor_address']}<br/>{invoice['tax_label']}: {invoice['tax_id']}", styles["BodyText"]),
          Paragraph(f"<b>INVOICE</b><br/>Invoice number: {invoice['number']}<br/>Invoice date: {invoice['date']:%d %B %Y}<br/>Due date: {invoice['due']:%d %B %Y}", styles["BodyText"])]],
        colWidths=[260, 220],
        hAlign="LEFT",
    )

    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for description, qty, unit_price in invoice["items"]:
        rows.append([description, str(qty), f"{symbol}{unit_price:,.2f}", f"{symbol}{qty * unit_price:,.2f}"])
    subtotal = sum(qty * unit_price for _, qty, unit_price in invoice["items"])
    tax = round(subtotal * invoice["tax_rate"], 2)
    rows += [
        ["", "", "Subtotal", f"{symbol}{subtotal:,.2f}"],
        ["", "", f"{invoice['tax_name']} ({invoice['tax_rate']:.0%})", f"{symbol}{tax:,.2f}"],
        ["", "", "Total due", f"{symbol}{subtotal + tax:,.2f} {invoice['currency']}"],
    ]
    items_table = Table(rows, colWidths=[250, 50, 90, 100], hAlign="LEFT")
    items_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEABOVE", (2, -3), (-1, -3), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))

    doc.build([
        header,
        Spacer(1, 18),
        Paragraph(f"<b>Bill to:</b> {invoice['bill_to']}", styles["BodyText"]),
        Spacer(1, 18),
        items_table,
        Spacer(1, 18),
        Paragraph(f"Payment method: {invoice['payment']}", styles["BodyText"]),
        Paragraph("Fictional sample invoice for demonstration purposes only.", styles["Italic"]),
    ])


def build_receipt_image(file_name: str):
    image = Image.new("RGB", (620, 820), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        bold = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        font = bold = ImageFont.load_default(size=22)

    receipt_date = date(2026, 9, 26)
    assert receipt_date.weekday() == 5, "receipt should be dated on a Saturday"

    # (font, left-aligned text, right-aligned amount)
    lines = [
        (bold, "QuickFix Maintenance", ""),
        (font, "Rue de la Loi 42, 1040 Brussels", ""),
        (font, "", ""),
        (font, "RECEIPT", ""),
        (font, f"Date: {receipt_date:%d/%m/%Y}", ""),
        (font, "", ""),
        (font, "Emergency boiler replacement", "€5,200.00"),
        (font, "Call-out fee (weekend)", "€700.00"),
        (font, "", ""),
        (bold, "TOTAL", "€5,900.00"),
        (font, "", ""),
        (font, "Paid: cash", ""),
        (font, "", ""),
        (font, "Fictional sample receipt for demo use only.", ""),
    ]
    y = 50
    for line_font, text, amount in lines:
        draw.text((40, y), text, fill="black", font=line_font)
        if amount:
            draw.text((580, y), amount, fill="black", font=line_font, anchor="ra")
        y += 48
    draw.line((40, 50 + 8 * 48 + 20, 580, 50 + 8 * 48 + 20), fill="black", width=2)
    image.save(SAMPLES_DIR / file_name)


def main():
    SAMPLES_DIR.mkdir(exist_ok=True)

    northwind_date = date(2026, 9, 15)
    atlas_date = date(2026, 9, 22)
    assert northwind_date.weekday() < 5 and atlas_date.weekday() < 5, "PDF samples should be dated on weekdays"

    build_pdf_invoice("northwind_office_supplies.pdf", {
        "vendor": "Northwind Office Supplies Ltd",
        "vendor_address": "14 Market Street, Manchester, M1 1PT, United Kingdom",
        "tax_label": "VAT No", "tax_id": "GB 123 4567 89",
        "number": "NW-2026-0915", "date": northwind_date, "due": date(2026, 10, 15),
        "bill_to": "Contoso Finance Ltd, 1 Canada Square, London E14 5AB",
        "currency": "GBP", "symbol": "£", "tax_name": "VAT", "tax_rate": 0.20,
        "items": [("A4 printer paper, 5 reams", 4, 21.50), ("Ergonomic desk chair", 1, 79.99), ("Whiteboard markers, pack of 12", 3, 6.99)],
        "payment": "Bank transfer",
    })
    build_pdf_invoice("atlas_cloud_services_usd.pdf", {
        "vendor": "Atlas Cloud Services Inc.",
        "vendor_address": "500 Howard Street, San Francisco, CA 94105, USA",
        "tax_label": "EIN", "tax_id": "94-1234567",
        "number": "ACS-88213", "date": atlas_date, "due": date(2026, 10, 22),
        "bill_to": "Contoso Finance Ltd, 1 Canada Square, London E14 5AB",
        "currency": "USD", "symbol": "$", "tax_name": "Sales tax", "tax_rate": 0.08,
        "items": [("Cloud hosting, September 2026", 1, 1650.00), ("Managed database, September 2026", 1, 480.00), ("Premium support plan", 1, 199.00)],
        "payment": "Card",
    })
    build_receipt_image("quickfix_maintenance_receipt.png")
    print(f"Samples written to {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
