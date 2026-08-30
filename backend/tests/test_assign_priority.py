"""Unit tests for the deterministic priority rule engine.

No Firestore, no Gemini: evaluate_priority is a pure function of the reports
already linked to an incident, so every case here is exact and reproducible.
"""

from __future__ import annotations

from models.common import IssueCategory, Location
from models.report import Report
from models.common import Priority
from models.triage import TriageResult
from tools.assign_priority import evaluate_priority


def _report(signals: list[str] | None = None, emergency: bool = False) -> Report:
    """Build a minimal triaged report with the given evidence."""
    return Report(
        campus_id="test-campus",
        description="A facility problem.",
        location=Location(building_id="bldg_test"),
        triage=TriageResult(
            issue_type=IssueCategory.PLUMBING,
            severity_signals=signals or [],
            is_potential_emergency=emergency,
        ),
    )


def test_no_reports_is_low_priority() -> None:
    priority, reasons = evaluate_priority([])
    assert priority is Priority.LOW
    assert "0 reports with no urgency signals" in reasons[0]


def test_single_report_no_signals_is_low() -> None:
    priority, reasons = evaluate_priority([_report()])
    assert priority is Priority.LOW
    assert "1 report with no urgency signals" in reasons[0]


def test_severity_signals_alone_raise_to_medium() -> None:
    priority, reasons = evaluate_priority([_report(signals=["water pouring out"])])
    assert priority is Priority.MEDIUM
    assert any("urgency signal" in reason for reason in reasons)


def test_two_corroborating_reports_raise_to_medium() -> None:
    priority, _ = evaluate_priority([_report(), _report()])
    assert priority is Priority.MEDIUM


def test_four_corroborating_reports_raise_to_high() -> None:
    priority, _ = evaluate_priority([_report(), _report(), _report(), _report()])
    assert priority is Priority.HIGH


def test_one_emergency_report_raises_to_high() -> None:
    priority, reasons = evaluate_priority(
        [_report(signals=["smoke visible"], emergency=True)]
    )
    assert priority is Priority.HIGH
    assert any("posing danger" in reason for reason in reasons)


def test_two_independent_emergency_reports_raise_to_critical() -> None:
    priority, reasons = evaluate_priority(
        [
            _report(signals=["water pouring out"], emergency=True),
            _report(signals=["saw a spark"], emergency=True),
        ]
    )
    assert priority is Priority.CRITICAL
    assert any("multiple independent reports describe danger" in r for r in reasons)


def test_emergency_flag_without_a_signal_does_not_count_as_emergency_evidence() -> None:
    """A report can be flagged a possible emergency yet quote no condition.

    That flag alone must not count toward the emergency thresholds: only one
    of the two reports here actually pairs the flag with a quoted signal, so
    this must land on high, not critical.
    """
    reports = [
        _report(signals=["water pouring out"], emergency=True),
        _report(signals=[], emergency=True),  # flagged, but nothing quoted
    ]
    priority, reasons = evaluate_priority(reports)
    assert priority is Priority.HIGH
    assert not any("multiple independent reports describe danger" in r for r in reasons)


def test_priority_never_decreases_within_one_evaluation() -> None:
    """Corroboration and danger evidence stack; the result is monotonic.

    Four corroborating reports would ordinarily be HIGH; adding severity
    signals cannot pull the result back down to MEDIUM.
    """
    reports = [_report(signals=["banging on the door"]) for _ in range(4)]
    priority, _ = evaluate_priority(reports)
    assert priority is Priority.HIGH


def test_reevaluation_is_idempotent_on_unchanged_evidence() -> None:
    reports = [_report(signals=["leak"], emergency=True)]
    first = evaluate_priority(reports)
    second = evaluate_priority(reports)
    assert first == second
