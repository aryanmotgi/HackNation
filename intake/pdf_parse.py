"""Deterministic PDF price-sheet parser — NO AI.

We control the price-sheet / PO format (see intake/sample_pdf.py), so we parse it
with pdfplumber + regex. Every field is best-effort: anything not found comes back
as None, and the question engine (intake/questions.py) fills the gaps.

    parse_price_sheet(path_or_bytes) -> dict  # draft deal fields

── Where a vision model would slot in later ──────────────────────────────────
Real manufacturers' price sheets vary wildly in layout. When we support arbitrary
PDFs, this function becomes the FALLBACK: if the deterministic regex extraction
finds too few fields (see `_confidence`), hand the page image to a vision model to
extract the same dict, then run it through the exact same validation. The contract
(the returned dict shape) stays identical, so nothing downstream changes.
"""

from __future__ import annotations

import io
import re
from typing import Any, Optional, Union

import pdfplumber

# Field label -> regex capturing the value. Case-insensitive, tolerant of spacing.
_PATTERNS = {
    "product":       re.compile(r"Product\s*:\s*(.+)", re.I),
    "sku":           re.compile(r"SKU\s*:\s*(\S+)", re.I),
    "quantity_line": re.compile(r"(?:Minimum\s*Order|Quantity)\s*:\s*([\d,]+)\s*([A-Za-z]+)?", re.I),
    "opening_price": re.compile(r"Opening\s*Price\s*:\s*([\d.]+)", re.I),
    "floor_price":   re.compile(r"(?:Hard\s*Floor|Floor\s*Price)\s*:\s*([\d.]+)", re.I),
    "target_price":  re.compile(r"(?:Target\s*(?:Close|Price))\s*:\s*([\d.]+)", re.I),
    "currency":      re.compile(r"Currency\s*:\s*([A-Za-z]{3})", re.I),
    "lead_time":     re.compile(r"Lead\s*Time\s*:\s*(\d+)", re.I),
    "payment_terms": re.compile(r"Payment\s*Terms\s*:\s*(.+)", re.I),
}


def _extract_text(source: Union[str, bytes]) -> str:
    stream = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    with pdfplumber.open(stream) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_price_sheet(source: Union[str, bytes]) -> dict[str, Any]:
    """Parse a controlled-format price sheet into draft deal fields.

    `source` is a filesystem path or raw PDF bytes. Missing fields are None.
    Returns: {product, quantity, unit, floor_price, target_price, currency,
              payment_terms, _found} where _found lists the fields we extracted.
    """
    text = _extract_text(source)
    draft: dict[str, Any] = {
        "product": None, "sku": None, "quantity": None, "unit": "units",
        "opening_price": None, "floor_price": None, "target_price": None,
        "currency": None, "lead_time_days": None, "payment_terms": None,
    }
    found: list[str] = []

    if m := _PATTERNS["product"].search(text):
        draft["product"] = m.group(1).strip(); found.append("product")
    if m := _PATTERNS["sku"].search(text):
        draft["sku"] = m.group(1).strip(); found.append("sku")
    if m := _PATTERNS["quantity_line"].search(text):
        q = _num(m.group(1))
        if q is not None:
            draft["quantity"] = int(q); found.append("quantity")
        if m.group(2):
            draft["unit"] = m.group(2).strip().lower()
    if m := _PATTERNS["opening_price"].search(text):
        draft["opening_price"] = _num(m.group(1)); found.append("opening_price")
    if m := _PATTERNS["floor_price"].search(text):
        draft["floor_price"] = _num(m.group(1)); found.append("floor_price")
    if m := _PATTERNS["target_price"].search(text):
        draft["target_price"] = _num(m.group(1)); found.append("target_price")
    if m := _PATTERNS["currency"].search(text):
        draft["currency"] = m.group(1).upper(); found.append("currency")
    if m := _PATTERNS["lead_time"].search(text):
        draft["lead_time_days"] = int(_num(m.group(1))); found.append("lead_time_days")
    if m := _PATTERNS["payment_terms"].search(text):
        draft["payment_terms"] = m.group(1).strip(); found.append("payment_terms")

    draft["_found"] = found
    return draft
