"""ADK tool: advance an incident through its lifecycle."""

from __future__ import annotations

from typing import Any


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
            ``in_progress``, ``on_hold``, ``resolved``, or ``closed``.
        notes: Optional context; required when resolving, where it becomes the
            incident's resolution notes.

    Returns:
        A dict with ``incident_id``, ``status``, and ``previous_status``; or
        ``{"error": ...}`` if the transition is not allowed.
    """
    raise NotImplementedError
