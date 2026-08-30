"""Unit tests for the incident status state machine.

ALLOWED_TRANSITIONS is checked directly as the single source of truth, then
update_incident_status itself is exercised with Firestore calls stubbed out,
since its job is to enforce that table plus the resolution-notes rule.
"""

from __future__ import annotations

import importlib

from models.common import IncidentStatus, IssueCategory, Location
from models.incident import Incident
from tools.update_incident_status import ALLOWED_TRANSITIONS, update_incident_status

# See test_escalate_overdue_incidents.py: tools/__init__.py re-exports this
# module's function under the module's own name, shadowing the submodule on
# the `tools` package, so monkeypatching needs the real module from
# sys.modules rather than an attribute lookup through `tools`.
status_module = importlib.import_module("tools.update_incident_status")


def _incident(status: IncidentStatus) -> Incident:
    return Incident(
        campus_id="test-campus",
        title="Test incident",
        summary="A test incident.",
        category=IssueCategory.PLUMBING,
        location=Location(building_id="bldg_test"),
        status=status,
    )


# --- The transition table itself --------------------------------------------


def test_every_status_has_a_table_entry() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(IncidentStatus)


def test_closed_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[IncidentStatus.CLOSED] == frozenset()


def test_resolved_can_only_close() -> None:
    assert ALLOWED_TRANSITIONS[IncidentStatus.RESOLVED] == frozenset(
        {IncidentStatus.CLOSED}
    )


def test_escalated_cannot_drop_back_to_open() -> None:
    assert IncidentStatus.OPEN not in ALLOWED_TRANSITIONS[IncidentStatus.ESCALATED]


def test_escalated_can_still_progress_and_resolve() -> None:
    allowed = ALLOWED_TRANSITIONS[IncidentStatus.ESCALATED]
    assert IncidentStatus.IN_PROGRESS in allowed
    assert IncidentStatus.RESOLVED in allowed


def test_open_reaches_escalated_directly() -> None:
    """The overdue sweep escalates straight from OPEN when dispatch stalled.

    Omitting this from the table would make the sweep's own write illegal.
    """
    assert IncidentStatus.ESCALATED in ALLOWED_TRANSITIONS[IncidentStatus.OPEN]


def test_no_status_can_transition_to_itself_in_the_table() -> None:
    """Self-transitions are handled as a no-op by the tool, not by this table."""
    for status, allowed in ALLOWED_TRANSITIONS.items():
        assert status not in allowed


# --- The tool, with Firestore stubbed out -----------------------------------


def test_illegal_transition_is_rejected(monkeypatch) -> None:
    incident = _incident(IncidentStatus.CLOSED)
    monkeypatch.setattr(status_module, "get_incident", lambda incident_id: incident)

    result = update_incident_status(incident.id, status=IncidentStatus.OPEN.value)

    assert "error" in result
    assert "Cannot move incident" in result["error"]


def test_unknown_status_is_rejected(monkeypatch) -> None:
    incident = _incident(IncidentStatus.OPEN)
    monkeypatch.setattr(status_module, "get_incident", lambda incident_id: incident)

    result = update_incident_status(incident.id, status="on_fire")

    assert "error" in result
    assert "Unknown status" in result["error"]


def test_resolving_without_notes_is_rejected(monkeypatch) -> None:
    incident = _incident(IncidentStatus.ASSIGNED)
    monkeypatch.setattr(status_module, "get_incident", lambda incident_id: incident)

    result = update_incident_status(incident.id, status=IncidentStatus.RESOLVED.value)

    assert "error" in result
    assert "requires notes" in result["error"]


def test_legal_transition_writes_and_records_a_decision(monkeypatch) -> None:
    incident = _incident(IncidentStatus.OPEN)
    updates: dict[str, object] = {}
    decisions: list[object] = []

    monkeypatch.setattr(status_module, "get_incident", lambda incident_id: incident)
    monkeypatch.setattr(
        status_module,
        "update_incident",
        lambda incident_id, fields: updates.update(fields) or incident,
    )
    monkeypatch.setattr(
        status_module, "record_decision", lambda decision: decisions.append(decision)
    )

    result = update_incident_status(incident.id, status=IncidentStatus.ASSIGNED.value)

    assert result["changed"] is True
    assert result["previous_status"] == IncidentStatus.OPEN.value
    assert updates["status"] == IncidentStatus.ASSIGNED.value
    assert len(decisions) == 1


def test_same_status_is_a_no_op(monkeypatch) -> None:
    incident = _incident(IncidentStatus.ASSIGNED)
    monkeypatch.setattr(status_module, "get_incident", lambda incident_id: incident)

    result = update_incident_status(incident.id, status=IncidentStatus.ASSIGNED.value)

    assert result["changed"] is False
