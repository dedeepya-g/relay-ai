"""ADK tool: merge a duplicate report into an existing incident."""

from __future__ import annotations

from typing import Any


def merge_report_into_incident(report_id: str, incident_id: str) -> dict[str, Any]:
    """Attach a duplicate report to the incident it describes.

    Call this when ``find_duplicate_incident`` matched an existing incident.
    Links the report as supporting evidence, folds any new detail into the
    incident summary, and carries over the report's photo. Corroborating
    reports are a severity signal, so re-check priority after merging.

    Args:
        report_id: Id of the duplicate report.
        incident_id: Id of the incident it belongs to.

    Returns:
        A dict with ``incident_id``, ``report_ids``, ``report_count``, and the
        updated ``summary``; or ``{"error": ...}`` if either id is unknown.
    """
    raise NotImplementedError
