"""Tier-1 guard for the S12 verification audit (analysis/verify.py).

Asserts the audit itself reports no hard FAIL on the committed repo state — so a
future change that breaks schema conformance, the validated-only gate, or the
deterministic-chain reproducibility is caught by the suite, not only by a manual run.
"""

from __future__ import annotations

from analysis import verify


def test_audit_has_no_hard_failures():
    checks = verify.run_all()
    failures = [c for c in checks if c.status == "FAIL"]
    assert not failures, "verification FAILs: " + "; ".join(f"{c.name}: {c.detail}" for c in failures)


def test_validation_gate_checks_pass():
    # The §6 gate-integrity checks specifically must all PASS (no agent self-certification).
    gate = [c for c in verify.run_all() if c.name.startswith("gate.")]
    assert gate and all(c.status == "PASS" for c in gate)


def test_known_gaps_documented():
    # The three carried gaps the human asked to record must be present in the report data.
    titles = " ".join(t for t, _ in verify.KNOWN_GAPS)
    assert "DEC-036" in titles   # RQ2 ACLED-2026
    assert "DEC-035" in titles   # Hasakah-June flood flag
    assert "DEC-039" in titles   # first-half-2026 case-study scope
