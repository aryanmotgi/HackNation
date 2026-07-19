"""Generate a sample price-sheet PDF in our controlled format (reportlab).

Because we control the format, the deterministic parser (intake/pdf_parse.py) can
read this exactly. Use it to demo the intake wizard end to end.

    python -m intake.sample_pdf            # writes samples/price_sheet_sample.pdf
    price_sheet_pdf(fields) -> bytes       # generate in-memory for tests
"""

from __future__ import annotations

import io
import os
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

DEFAULT_FIELDS = {
    "product": "Cotton T-shirts",
    "sku": "TS-CTN-180",
    "quantity": "10000 units",
    "opening_price": "4.40 USD",
    "target_price": "4.00 USD",
    "floor_price": "3.20 USD",
    "currency": "USD",
    "lead_time": "25 days",
    "payment_terms": "30% deposit, 70% before shipment",
}

# Field label order as printed on the sheet — matches the parser's regex labels.
_LINES = [
    ("Product", "product"),
    ("SKU", "sku"),
    ("Minimum Order", "quantity"),
    ("Opening Price", "opening_price"),
    ("Target Close", "target_price"),
    ("Hard Floor", "floor_price"),
    ("Currency", "currency"),
    ("Lead Time", "lead_time"),
    ("Payment Terms", "payment_terms"),
]


def price_sheet_pdf(fields: dict[str, Any] | None = None) -> bytes:
    """Render a controlled-format price sheet to PDF bytes."""
    f = {**DEFAULT_FIELDS, **(fields or {})}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 90, "LOOMHAUS MANUFACTURING — PRICE SHEET")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 112, "Confidential · internal negotiation reference")

    y = height - 170
    c.setFont("Helvetica", 13)
    for label, key in _LINES:
        if f.get(key) is not None:
            c.drawString(90, y, f"{label}: {f[key]}")
            y -= 26

    c.showPage()
    c.save()
    return buf.getvalue()


def main() -> None:
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "price_sheet_sample.pdf")
    with open(path, "wb") as fh:
        fh.write(price_sheet_pdf())
    print(f"Wrote sample price sheet -> {path}")


if __name__ == "__main__":
    main()
