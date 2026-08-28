"""ADK tool: dispatch a work order to the assigned team."""

from __future__ import annotations

from typing import Any


def create_work_order(incident_id: str) -> dict[str, Any]:
    """Dispatch a work order for a routed incident.

    Call this once an incident has a team and a priority. Writes field-ready
    instructions covering the location, the problem, and any access notes, then
    moves the incident to ``assigned``.

    Args:
        incident_id: Id of the incident to dispatch.

    Returns:
        A dict with ``work_order_id``, ``incident_id``, ``team_id``,
        ``due_at``, and ``instructions``; or ``{"error": ...}`` if the incident
        has no assigned team or already has an open work order.
    """
    raise NotImplementedError
