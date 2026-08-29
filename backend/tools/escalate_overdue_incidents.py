"""ADK tool: escalate incidents that have missed their SLA.

The sweep is entirely rule-based. Whether a deadline passed is arithmetic, and
who gets told is campus policy that was written down in advance -- neither is a
judgment, and every escalation it records carries ``model=None`` to say so. An
escalation is the claim a facilities manager is most likely to be challenged
on, so it has to be reproducible from the incident and the policy alone.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from models.campus_config import CampusConfig
from models.common import (
    DecisionActor,
    DecisionType,
    IncidentStatus,
    IssueCategory,
    Priority,
    WorkOrderStatus,
    new_id,
    utc_now,
)
from models.decision import Decision
from models.incident import Incident
from models.work_order import StatusChange, WorkOrder, ticket_number
from services.firestore_service import (
    create_work_order,
    get_campus_config,
    list_overdue_incidents,
    list_work_orders_for_incident,
    record_decision,
    update_incident,
    update_work_order,
)
from tools.update_incident_status import ALLOWED_TRANSITIONS

logger = logging.getLogger(__name__)

#: Priorities at which a breach pulls in a second team. A critical fault still
#: unresolved past its deadline has stopped being only a maintenance problem,
#: and the team that owns safety is the one that can close a corridor or post a
#: warning while the original crew works.
SECOND_RESPONDER_PRIORITIES = frozenset({Priority.CRITICAL})


def _second_responder(config: CampusConfig, incident: Incident) -> str | None:
    """Return a team to bring in alongside the assigned one, if the rule applies.

    Deterministic: critical, overdue, and the safety-owning team is not already
    the one working it.
    """
    if incident.priority not in SECOND_RESPONDER_PRIORITIES:
        return None
    for team in config.teams:
        if IssueCategory.SAFETY in team.categories:
            return team.id if team.id != incident.assigned_team_id else None
    return None


def _mark_work_orders(incident: Incident, level: int, overdue_by: timedelta) -> list[str]:
    """Append the breach to every live work order's history."""
    touched: list[str] = []
    for work_order in list_work_orders_for_incident(incident.id):
        if work_order.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
            continue
        history = [*work_order.status_history, StatusChange(
            status=work_order.status,
            at=utc_now(),
            note=f"Escalated to level {level}; "
            f"{int(overdue_by.total_seconds() // 60)} minutes past deadline.",
        )]
        update_work_order(
            work_order.id,
            {"status_history": [item.to_firestore() for item in history]},
        )
        touched.append(work_order.ticket)
    return touched


def _dispatch_second_responder(incident: Incident, team_id: str) -> str | None:
    """Raise a work order for the supporting team, unless one already exists."""
    if any(
        work_order.team_id == team_id
        for work_order in list_work_orders_for_incident(incident.id)
    ):
        return None

    work_order_id = new_id("wo")
    work_order = create_work_order(
        WorkOrder(
            id=work_order_id,
            ticket=ticket_number(work_order_id),
            campus_id=incident.campus_id,
            incident_id=incident.id,
            team_id=team_id,
            priority=incident.priority,
            instructions=(
                f"Supporting response for {incident.title}.\n"
                "This incident passed its deadline while critical. Make the "
                "area safe and control access while the assigned team works."
            ),
            status=WorkOrderStatus.PENDING,
            status_history=[
                StatusChange(
                    status=WorkOrderStatus.PENDING,
                    at=utc_now(),
                    note="Brought in on escalation of a critical incident.",
                )
            ],
            due_at=incident.sla_due_at,
        )
    )
    return work_order.ticket


def escalate_overdue_incidents(campus_id: str) -> dict[str, Any]:
    """Find incidents past their SLA deadline and escalate them.

    Call this on a schedule rather than in response to a report. Applies the
    campus escalation policy: waits out the grace period, honours the repeat
    interval between successive raises, and stops once an incident reaches the
    policy's maximum level.

    Args:
        campus_id: Campus to sweep.

    Returns:
        A dict with ``campus_id``, ``checked_count``, ``escalated_count``, and
        ``escalations`` -- one entry per incident with its id, new escalation
        level, minutes past deadline, and any supporting team brought in.
    """
    config = get_campus_config(campus_id)
    if config is None:
        return {"error": f"No campus configuration for {campus_id!r}."}

    policy = config.escalation_policy
    now = utc_now()
    candidates = list_overdue_incidents(campus_id, as_of=now)
    escalations: list[dict[str, Any]] = []

    for incident in candidates:
        overdue_by = now - incident.sla_due_at
        if overdue_by < timedelta(minutes=policy.grace_period_minutes):
            continue
        if incident.escalation_level >= policy.max_level:
            continue
        if incident.last_escalated_at is not None and now - incident.last_escalated_at < timedelta(
            minutes=policy.repeat_interval_minutes
        ):
            continue

        # The sweep writes status itself, in one update alongside the level and
        # timestamp, rather than calling update_incident_status: that tool
        # records a RESOLUTION decision and would split this into two writes,
        # and escalation records its own decision below. Consulting the shared
        # table keeps the rule in one place even though the write is not.
        # Re-escalation is a self-transition, which the table does not list.
        if incident.status is not IncidentStatus.ESCALATED and (
            IncidentStatus.ESCALATED
            not in ALLOWED_TRANSITIONS.get(incident.status, frozenset())
        ):
            logger.warning(
                "Skipping incident %s: %s cannot be escalated.",
                incident.id,
                incident.status.value,
            )
            continue

        level = incident.escalation_level + 1
        minutes_over = int(overdue_by.total_seconds() // 60)

        second_team = _second_responder(config, incident)
        supporting_ticket = (
            _dispatch_second_responder(incident, second_team) if second_team else None
        )
        tickets = _mark_work_orders(incident, level, overdue_by)

        update_incident(
            incident.id,
            {
                "status": IncidentStatus.ESCALATED.value,
                "escalation_level": level,
                "last_escalated_at": now,
            },
        )

        rationale = (
            f"{incident.priority.value.title()} incident passed its "
            f"{policy.grace_period_minutes}-minute grace period and is "
            f"{minutes_over} minutes past its deadline with no resolution. "
            f"Raised to escalation level {level} of {policy.max_level} and "
            f"{', '.join(policy.notify_on_escalation) or 'the escalation contacts'} "
            "were notified."
        )
        if supporting_ticket:
            rationale += (
                f" A critical incident this far past deadline is a safety "
                f"exposure, so {second_team} was brought in on {supporting_ticket}."
            )

        record_decision(
            Decision(
                campus_id=campus_id,
                decision_type=DecisionType.ESCALATION,
                decided_by=DecisionActor.RULE,
                subject_type="incidents",
                subject_id=incident.id,
                outcome=f"escalated to level {level}",
                rationale=rationale,
                tool_name="escalate_overdue_incidents",
                model=None,
                inputs={
                    "minutes_past_deadline": minutes_over,
                    "priority": incident.priority.value,
                    "assigned_team_id": incident.assigned_team_id,
                    "work_order_tickets": tickets,
                },
            )
        )

        escalations.append(
            {
                "incident_id": incident.id,
                "title": incident.title,
                "escalation_level": level,
                "minutes_past_deadline": minutes_over,
                "supporting_team_id": second_team,
                "supporting_ticket": supporting_ticket,
                "work_order_tickets": tickets,
            }
        )
        logger.info(
            "Escalated %s to level %d (%d minutes over)",
            incident.id,
            level,
            minutes_over,
        )

    return {
        "campus_id": campus_id,
        "checked_count": len(candidates),
        "escalated_count": len(escalations),
        "escalations": escalations,
    }
