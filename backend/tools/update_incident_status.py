"""ADK tool: advance an incident through its lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from models.common import DecisionActor, DecisionType, IncidentStatus, utc_now
from models.decision import Decision
from services.firestore_service import get_incident, record_decision, update_incident

logger = logging.getLogger(__name__)

#: Legal transitions. Written out rather than derived so that an illegal move
#: -- reopening a resolved incident, closing one nobody worked -- fails at the
#: boundary instead of quietly rewriting history a team acted on.
ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    # ESCALATED is reachable from OPEN because the overdue sweep escalates on
    # the deadline alone, and an incident whose dispatch failed sits in OPEN
    # while its clock still runs. Omitting it here would have made the sweep's
    # own write illegal by this table.
    IncidentStatus.OPEN: frozenset(
        {
            IncidentStatus.ASSIGNED,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.ON_HOLD,
            IncidentStatus.ESCALATED,
        }
    ),
    IncidentStatus.ASSIGNED: frozenset(
        {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.ON_HOLD,
            IncidentStatus.ESCALATED,
            IncidentStatus.RESOLVED,
        }
    ),
    IncidentStatus.IN_PROGRESS: frozenset(
        {IncidentStatus.ON_HOLD, IncidentStatus.ESCALATED, IncidentStatus.RESOLVED}
    ),
    IncidentStatus.ON_HOLD: frozenset(
        {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.ESCALATED,
            IncidentStatus.RESOLVED,
        }
    ),
    # An escalated incident is still live work, so it can progress or be
    # resolved. It cannot drop back to open: the breach happened.
    IncidentStatus.ESCALATED: frozenset(
        {IncidentStatus.IN_PROGRESS, IncidentStatus.ON_HOLD, IncidentStatus.RESOLVED}
    ),
    IncidentStatus.RESOLVED: frozenset({IncidentStatus.CLOSED}),
    IncidentStatus.CLOSED: frozenset(),
}


def update_incident_status(
    incident_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    """Move an incident to a new lifecycle status.

    Call this when a team acknowledges, starts, pauses, or finishes work.
    Rejects transitions that are not legal from the current status, and stamps
    ``resolved_at`` or ``closed_at`` when the incident reaches those states.

    Args:
        incident_id: Id of the incident to update.
        status: Target status -- one of ``open``, ``assigned``,
            ``in_progress``, ``on_hold``, ``escalated``, ``resolved``, or
            ``closed``.
        notes: Optional context; required when resolving, where it becomes the
            incident's resolution notes.

    Returns:
        A dict with ``incident_id``, ``status``, and ``previous_status``; or
        ``{"error": ...}`` if the transition is not allowed.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id!r}."}

    try:
        target = IncidentStatus(status)
    except ValueError:
        return {
            "error": f"Unknown status {status!r}; expected one of "
            f"{sorted(item.value for item in IncidentStatus)}."
        }

    if target is incident.status:
        return {
            "incident_id": incident_id,
            "status": target.value,
            "previous_status": incident.status.value,
            "changed": False,
        }

    allowed = ALLOWED_TRANSITIONS.get(incident.status, frozenset())
    if target not in allowed:
        return {
            "error": f"Cannot move incident {incident_id!r} from "
            f"{incident.status.value!r} to {target.value!r}. Allowed from "
            f"{incident.status.value!r}: "
            f"{sorted(item.value for item in allowed) or 'nothing'}."
        }

    if target is IncidentStatus.RESOLVED and not notes:
        return {
            "error": "Resolving an incident requires notes describing what was "
            "done."
        }

    fields: dict[str, object] = {"status": target.value}
    if target is IncidentStatus.RESOLVED:
        fields["resolved_at"] = utc_now()
        fields["resolution_notes"] = notes
    elif target is IncidentStatus.CLOSED:
        fields["closed_at"] = utc_now()

    update_incident(incident_id, fields)
    record_decision(
        Decision(
            campus_id=incident.campus_id,
            decision_type=DecisionType.RESOLUTION,
            decided_by=DecisionActor.RULE,
            subject_type="incidents",
            subject_id=incident_id,
            outcome=f"{incident.status.value} to {target.value}",
            rationale=notes
            or f"Status moved from {incident.status.value} to {target.value}.",
            tool_name="update_incident_status",
            model=None,
        )
    )

    return {
        "incident_id": incident_id,
        "status": target.value,
        "previous_status": incident.status.value,
        "changed": True,
    }
