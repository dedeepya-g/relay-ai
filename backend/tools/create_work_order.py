"""ADK tool: dispatch a work order to the assigned team."""

from __future__ import annotations

import logging
from typing import Any

from models.common import IncidentStatus, WorkOrderStatus, new_id, utc_now
from models.incident import Incident
from models.work_order import StatusChange, WorkOrder, ticket_number
from services.firestore_service import (
    create_work_order as persist_work_order,
    get_campus_config,
    get_incident,
    list_reports_for_incident,
    list_work_orders_for_incident,
    update_incident,
)

logger = logging.getLogger(__name__)

#: Statuses in which a work order is still someone's job. A second work order
#: for the same team is only warranted once these are all closed out.
LIVE_WORK_ORDER_STATUSES = frozenset(
    {
        WorkOrderStatus.PENDING,
        WorkOrderStatus.ACKNOWLEDGED,
        WorkOrderStatus.IN_PROGRESS,
    }
)

MAX_INSTRUCTION_LENGTH = 2000


def _instructions(incident: Incident, building_name: str) -> str:
    """Write field-ready instructions from what reporters actually said.

    Composed rather than generated. A technician reading this on a phone needs
    the reporters' own words, not a paraphrase that could quietly drop the
    detail that matters -- and a dispatch note should read the same every time
    it is regenerated for the same evidence.
    """
    where = building_name
    if incident.location.room:
        where += f", room {incident.location.room}"
    elif incident.location.floor:
        where += f", floor {incident.location.floor}"

    lines = [
        f"Location: {where}",
        f"Problem: {incident.category.value}, priority {incident.priority.value}.",
        "",
        "Reported by:",
    ]
    for report in list_reports_for_incident(incident.id):
        spot = report.location.room or report.location.floor
        prefix = f"[{spot}] " if spot else ""
        lines.append(f'  - {prefix}"{report.description}"')

    return "\n".join(lines)[:MAX_INSTRUCTION_LENGTH]


def create_work_order(incident_id: str) -> dict[str, Any]:
    """Dispatch a work order for a routed incident.

    Call this once an incident has a team and a priority. Writes field-ready
    instructions covering the location and what each reporter said, then moves
    the incident to ``assigned``.

    Calling it again for an incident that already has live work returns that
    work order rather than raising a second one, so it is safe to run on every
    new report without dispatching a crew twice.

    Args:
        incident_id: Id of the incident to dispatch.

    Returns:
        A dict with ``work_order_id``, ``ticket``, ``incident_id``,
        ``team_id``, ``status``, ``due_at``, ``instructions``, and ``created``
        (false when an existing work order was returned); or
        ``{"error": ...}`` if the incident is missing or has no team.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id!r}."}
    if incident.assigned_team_id is None:
        return {
            "error": f"Incident {incident_id!r} has no assigned team; call "
            "route_to_team first."
        }

    existing = [
        work_order
        for work_order in list_work_orders_for_incident(incident_id)
        if work_order.team_id == incident.assigned_team_id
        and work_order.status in LIVE_WORK_ORDER_STATUSES
    ]
    if existing:
        work_order = existing[0]
        return {
            "work_order_id": work_order.id,
            "ticket": work_order.ticket,
            "incident_id": incident_id,
            "team_id": work_order.team_id,
            "status": work_order.status.value,
            "due_at": work_order.due_at.isoformat() if work_order.due_at else None,
            "instructions": work_order.instructions,
            "created": False,
        }

    config = get_campus_config(incident.campus_id)
    building_name = incident.location.building_id
    if config is not None:
        for building in config.buildings:
            if building.id == incident.location.building_id:
                building_name = building.name

    work_order_id = new_id("wo")
    work_order = persist_work_order(
        WorkOrder(
            id=work_order_id,
            ticket=ticket_number(work_order_id),
            campus_id=incident.campus_id,
            incident_id=incident_id,
            team_id=incident.assigned_team_id,
            priority=incident.priority,
            instructions=_instructions(incident, building_name),
            status=WorkOrderStatus.PENDING,
            status_history=[
                StatusChange(
                    status=WorkOrderStatus.PENDING,
                    at=utc_now(),
                    note=f"Dispatched to {incident.assigned_team_id}.",
                )
            ],
            due_at=incident.sla_due_at,
        )
    )

    # The work order already names its incident; this completes the link in the
    # other direction. Without it an incident reports no work orders even while
    # one is dispatched against it, and anything reading the incident -- a UI,
    # or a later tool -- cannot find the ticket. Folded into the same write as
    # the status flip so dispatch stays one update rather than two.
    fields: dict[str, object] = {
        "work_order_ids": list(dict.fromkeys([*incident.work_order_ids, work_order.id]))
    }
    if incident.status is IncidentStatus.OPEN:
        fields["status"] = IncidentStatus.ASSIGNED.value
    update_incident(incident_id, fields)

    return {
        "work_order_id": work_order.id,
        "ticket": work_order.ticket,
        "incident_id": incident_id,
        "team_id": work_order.team_id,
        "status": work_order.status.value,
        "due_at": work_order.due_at.isoformat() if work_order.due_at else None,
        "instructions": work_order.instructions,
        "created": True,
    }
