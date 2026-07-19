"""Intake — the manufacturer wizard that produces a job spec before negotiation.

PDF parse (deterministic) + hard-rule question engine (no AI) → one confirmed
JSON job spec that the negotiation agent reads at call time.

    from intake.job_spec import build_job_spec, validate_spec, save_job_spec, load_job_spec
    from intake.pdf_parse import parse_price_sheet
    from intake.questions import questions_for
"""
