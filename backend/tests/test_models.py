"""Unit tests for validators that guard against a malformed model response.

These are the seams where a language model's structured output meets a
strictly-typed Pydantic model: the response schema constrains the shape, but
these validators are what stop an unexpected value from silently corrupting
the record or crashing the request.
"""

from __future__ import annotations

from models.common import IssueCategory
from models.duplicate import DuplicateDecision, DuplicateVerdict
from models.triage import MissingField, TriageResult


# --- TriageResult.issue_type fallback ---------------------------------------


def test_known_category_string_is_accepted() -> None:
    result = TriageResult(issue_type="plumbing")
    assert result.issue_type is IssueCategory.PLUMBING


def test_known_category_is_normalized_for_case_and_whitespace() -> None:
    result = TriageResult(issue_type="  PLUMBING  ")
    assert result.issue_type is IssueCategory.PLUMBING


def test_unknown_category_falls_back_to_other() -> None:
    """The response schema should make this unreachable; treat it as data
    corruption rather than a crash if a model ever produces it anyway."""
    result = TriageResult(issue_type="haunted")
    assert result.issue_type is IssueCategory.OTHER


def test_already_an_enum_member_passes_through_unchanged() -> None:
    result = TriageResult(issue_type=IssueCategory.HVAC)
    assert result.issue_type is IssueCategory.HVAC


# --- TriageResult list cleanup -----------------------------------------------


def test_severity_signals_are_deduplicated_case_insensitively() -> None:
    result = TriageResult(
        issue_type="plumbing",
        severity_signals=["Water pouring", "water pouring", "", "  ", "sparks"],
    )
    assert result.severity_signals == ["Water pouring", "sparks"]


def test_missing_fields_are_deduplicated_preserving_order() -> None:
    result = TriageResult(
        issue_type="plumbing",
        missing_fields=[
            MissingField.FLOOR,
            MissingField.ROOM,
            MissingField.FLOOR,
        ],
    )
    assert result.missing_fields == [MissingField.FLOOR, MissingField.ROOM]


def test_confidence_note_is_truncated() -> None:
    result = TriageResult(issue_type="plumbing", confidence_note="x" * 1000)
    assert len(result.confidence_note) == 400


# --- DuplicateDecision contradiction clearing -------------------------------


def test_same_incident_keeps_its_matched_id() -> None:
    decision = DuplicateDecision(
        decision=DuplicateVerdict.SAME_INCIDENT, matched_incident_id="inc_abc123"
    )
    assert decision.matched_incident_id == "inc_abc123"


def test_different_incident_clears_a_contradictory_matched_id() -> None:
    """A model that answers different_incident while still naming one incident
    is contradicting itself; the id must not survive to be read naively."""
    decision = DuplicateDecision(
        decision=DuplicateVerdict.DIFFERENT_INCIDENT,
        matched_incident_id="inc_abc123",
    )
    assert decision.matched_incident_id is None


def test_needs_review_clears_a_contradictory_matched_id() -> None:
    decision = DuplicateDecision(
        decision=DuplicateVerdict.NEEDS_REVIEW, matched_incident_id="inc_abc123"
    )
    assert decision.matched_incident_id is None


def test_reasoning_is_truncated() -> None:
    decision = DuplicateDecision(
        decision=DuplicateVerdict.DIFFERENT_INCIDENT, reasoning="x" * 2000
    )
    assert len(decision.reasoning) == 1000
