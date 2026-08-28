"""ADK tool: open a new incident from a report."""

from __future__ import annotations

from typing import Any


def open_incident(report_id: str) -> dict[str, Any]:
    """Open a new incident for a report that is not a duplicate.

    Call this only when ``find_duplicate_incident`` found no match. Creates the
    incident from the report's triage result, links the report to it, and marks
    the report as triaged.

    Args:
        report_id: Id of the report opening the incident.

    Returns:
        A dict with ``incident_id``, ``title``, ``category``, and ``status``;
        or ``{"error": ...}`` if the report is missing or already linked.
    """
    raise NotImplementedError
