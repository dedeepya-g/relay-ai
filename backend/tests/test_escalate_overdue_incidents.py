"""Unit tests for the overdue sweep's escalation gate.

Firestore reads and writes are stubbed out entirely: what is under test is the
policy arithmetic -- grace period, repeat interval, and max level -- not
persistence. Every incident here is already past its `sla_due_at`; the only
question is whether the gate lets it through.
"""

from __future__ import annotations

import importlib
from datetime import timedelta

from models.campus_config import CampusConfig, EscalationPolicy, MaintenanceTeam
from models.common import IncidentStatus, IssueCategory, Location, Priority, utc_now
from models.incident import Incident

# tools/__init__.py re-exports each tool under its module's own name, which
# shadows the submodule as an attribute of the `tools` package. `import
# tools.escalate_overdue_incidents as sweep` would silently bind `sweep` to
# that re-exported function instead of the module; importlib reads the real
# module out of sys.modules regardless of what the package re-exports.
sweep = importlib.import_module("tools.escalate_overdue_incidents")


def _config(**policy_overrides: object) -> CampusConfig:
    return CampusConfig(
        id="test-campus",
        name="Test Campus",
        sla_minutes={
            Priority.CRITICAL: 2,
            Priority.HIGH: 5,
            Priority.MEDIUM: 15,
            Priority.LOW: 60,
        },
        escalation_policy=EscalationPolicy(**policy_overrides),
        teams=[
            MaintenanceTeam(
                id="team_plumbing", name="Plumbing", categories=[IssueCategory.PLUMBING]
            ),
            MaintenanceTeam(
                id="team_safety", name="Safety", categories=[IssueCategory.SAFETY]
            ),
        ],
    )


def _overdue_incident(
    *,
    minutes_overdue: int,
    escalation_level: int = 0,
    last_escalated_minutes_ago: int | None = None,
    priority: Priority = Priority.HIGH,
    status: IncidentStatus = IncidentStatus.ASSIGNED,
    assigned_team_id: str = "team_plumbing",
) -> Incident:
    now = utc_now()
    return Incident(
        campus_id="test-campus",
        title="Test incident",
        summary="A test incident.",
        category=IssueCategory.PLUMBING,
        location=Location(building_id="bldg_test"),
        priority=priority,
        status=status,
        assigned_team_id=assigned_team_id,
        sla_due_at=now - timedelta(minutes=minutes_overdue),
        escalation_level=escalation_level,
        last_escalated_at=(
            now - timedelta(minutes=last_escalated_minutes_ago)
            if last_escalated_minutes_ago is not None
            else None
        ),
    )


def _run(monkeypatch, config: CampusConfig, incidents: list[Incident]) -> dict:
    monkeypatch.setattr(sweep, "get_campus_config", lambda campus_id: config)
    monkeypatch.setattr(
        sweep, "list_overdue_incidents", lambda campus_id, as_of: incidents
    )
    monkeypatch.setattr(sweep, "list_work_orders_for_incident", lambda incident_id: [])
    monkeypatch.setattr(sweep, "update_work_order", lambda *a, **k: None)
    monkeypatch.setattr(sweep, "update_incident", lambda *a, **k: None)
    monkeypatch.setattr(sweep, "record_decision", lambda decision: decision)
    monkeypatch.setattr(
        sweep, "create_work_order", lambda work_order: work_order
    )
    return sweep.escalate_overdue_incidents("test-campus")


def test_within_grace_period_is_not_escalated(monkeypatch) -> None:
    config = _config(grace_period_minutes=15)
    incident = _overdue_incident(minutes_overdue=5)

    result = _run(monkeypatch, config, [incident])

    assert result["escalated_count"] == 0


def test_past_grace_period_with_no_prior_escalation_is_raised(monkeypatch) -> None:
    config = _config(grace_period_minutes=15)
    incident = _overdue_incident(minutes_overdue=20, escalation_level=0)

    result = _run(monkeypatch, config, [incident])

    assert result["escalated_count"] == 1
    assert result["escalations"][0]["escalation_level"] == 1


def test_already_at_max_level_is_not_raised_again(monkeypatch) -> None:
    config = _config(grace_period_minutes=15, max_level=3)
    incident = _overdue_incident(
        minutes_overdue=500, escalation_level=3, last_escalated_minutes_ago=200
    )

    result = _run(monkeypatch, config, [incident])

    assert result["escalated_count"] == 0


def test_escalated_too_recently_is_held_until_the_repeat_interval_passes(
    monkeypatch,
) -> None:
    config = _config(grace_period_minutes=15, repeat_interval_minutes=60)
    incident = _overdue_incident(
        minutes_overdue=100, escalation_level=1, last_escalated_minutes_ago=10
    )

    result = _run(monkeypatch, config, [incident])

    assert result["escalated_count"] == 0


def test_escalates_again_once_the_repeat_interval_has_passed(monkeypatch) -> None:
    config = _config(grace_period_minutes=15, repeat_interval_minutes=60)
    incident = _overdue_incident(
        minutes_overdue=100, escalation_level=1, last_escalated_minutes_ago=61
    )

    result = _run(monkeypatch, config, [incident])

    assert result["escalated_count"] == 1
    assert result["escalations"][0]["escalation_level"] == 2


def test_critical_breach_dispatches_a_safety_second_responder(monkeypatch) -> None:
    config = _config(grace_period_minutes=15)
    incident = _overdue_incident(
        minutes_overdue=20, escalation_level=0, priority=Priority.CRITICAL
    )

    result = _run(monkeypatch, config, [incident])

    escalation = result["escalations"][0]
    assert escalation["supporting_team_id"] == "team_safety"
    assert escalation["supporting_ticket"] is not None


def test_non_critical_breach_does_not_dispatch_a_second_responder(monkeypatch) -> None:
    config = _config(grace_period_minutes=15)
    incident = _overdue_incident(
        minutes_overdue=20, escalation_level=0, priority=Priority.HIGH
    )

    result = _run(monkeypatch, config, [incident])

    escalation = result["escalations"][0]
    assert escalation["supporting_team_id"] is None
    assert escalation["supporting_ticket"] is None


def test_safety_team_already_assigned_is_not_paged_as_its_own_backup(
    monkeypatch,
) -> None:
    config = _config(grace_period_minutes=15)
    incident = _overdue_incident(
        minutes_overdue=20,
        escalation_level=0,
        priority=Priority.CRITICAL,
        assigned_team_id="team_safety",
    )

    result = _run(monkeypatch, config, [incident])

    assert result["escalations"][0]["supporting_team_id"] is None
