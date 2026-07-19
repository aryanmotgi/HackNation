"""Intake smoke test — PDF parse → questions → build → validate → save → load.

Runs the deterministic intake pipeline end to end (no server, no AI).

Run:  .venv/bin/python -m tests.smoke_intake
"""

from __future__ import annotations

import os

from intake.sample_pdf import price_sheet_pdf
from intake.pdf_parse import parse_price_sheet
from intake.questions import questions_for, apply_answers
from intake.job_spec import (
    build_job_spec, validate_spec, save_job_spec, load_job_spec, DraftSpecError,
)

PASS = 0


def check(name: str, cond: bool) -> None:
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ok  {name}")


def main() -> None:
    print("[intake] parse a controlled-format PDF (in-memory)")
    draft = parse_price_sheet(price_sheet_pdf())
    check("product parsed", draft["product"] == "Cotton T-shirts")
    check("quantity parsed as int", draft["quantity"] == 10000)
    check("floor parsed", draft["floor_price"] == 3.20)
    check("target parsed", draft["target_price"] == 4.00)

    print("\n[intake] question engine skips PDF-filled fields")
    qs = questions_for(draft)
    ids = {q["id"] for q in qs}
    check("floor/target not asked (PDF had them)", "floor_price" not in ids and "target_price" not in ids)
    check("always-ask guardrails present",
          {"forbidden_terms", "walk_away_price", "escalation_trigger"} <= ids)

    print("\n[intake] a PDF missing the floor asks for it")
    partial = parse_price_sheet(price_sheet_pdf({"floor_price": None}))
    check("missing floor -> asked", "floor_price" in {q["id"] for q in questions_for(partial)})

    print("\n[intake] build + validate a confirmed spec")
    deal, hr, audit = apply_answers(draft, {
        "forbidden_terms": "exclusivity, consignment",
        "walk_away_price": "3.00",
        "escalation_trigger": "3 declining calls",
    })
    spec = build_job_spec(deal=deal, hard_rules=hr, questions=audit, source="pdf",
                          created_at="2026-07-18T12:00:00", status="confirmed")
    check("valid spec has no errors", validate_spec(spec) == [])
    check("hard-rule floor mirrors deal floor", spec["hard_rules"]["floor_price"] == 3.20)
    check("forbidden terms parsed to list", spec["hard_rules"]["forbidden_terms"] == ["exclusivity", "consignment"])
    check("audit records answer sources", {q["source"] for q in spec["questions"]} <= {"pdf", "user"})

    print("\n[intake] validation catches bad parses")
    bad = build_job_spec(deal={**deal, "floor_price": 5.0, "target_price": 4.0},
                         hard_rules=hr, questions=audit, source="pdf",
                         created_at="2026-07-18T12:00:00")
    check("floor > target flagged", any("floor" in e for e in validate_spec(bad)))
    zero = build_job_spec(deal={**deal, "quantity": 0}, hard_rules=hr, questions=audit,
                          source="pdf", created_at="2026-07-18T12:00:00")
    check("quantity 0 flagged", any("quantity" in e.lower() for e in validate_spec(zero)))

    print("\n[intake] save + load; loader refuses drafts")
    path = save_job_spec(spec, jobs_dir="/tmp/_intake_test_jobs")
    loaded = load_job_spec(path)
    check("confirmed spec loads", loaded["job_id"] == spec["job_id"])
    draft_spec = dict(spec, status="draft", job_id="draft_job")
    dpath = save_job_spec(draft_spec, jobs_dir="/tmp/_intake_test_jobs")
    try:
        load_job_spec(dpath); check("draft refused", False)
    except DraftSpecError:
        check("draft refused", True)
    os.remove(path); os.remove(dpath)

    print(f"\nALL {PASS} INTAKE CHECKS PASSED ✓")


if __name__ == "__main__":
    main()
