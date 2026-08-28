"""ADK tool: choose the maintenance team that owns an incident."""

from __future__ import annotations

from typing import Any


def route_to_team(incident_id: str) -> dict[str, Any]:
    """Route an incident to the maintenance team that should fix it.

    Call this after the incident has a category and priority. Matches the
    category against team ownership in the campus config and takes coverage
    hours into account, falling back to the configured default team when no
    team owns the category.

    Args:
        incident_id: Id of the incident to route.

    Returns:
        A dict with ``incident_id``, ``team_id``, ``team_name``, ``rationale``,
        and ``used_fallback``.
    """
    raise NotImplementedError
