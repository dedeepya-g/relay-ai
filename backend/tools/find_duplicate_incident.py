"""ADK tool: decide whether a report describes a known incident."""

from __future__ import annotations

from typing import Any


def find_duplicate_incident(report_id: str) -> dict[str, Any]:
    """Check whether a triaged report describes an already-tracked incident.

    Call this after ``triage_report`` and before opening a new incident.
    Shortlists recent open incidents in the same building, then compares them
    against the report to decide whether they describe the same underlying
    problem -- three reports of one flooded restroom, not three floods.

    Args:
        report_id: Id of the triaged report to match.

    Returns:
        A dict with ``report_id``, ``match_found``, ``incident_id`` (``None``
        when no match), ``confidence``, ``rationale``, and ``candidates``
        listing the incidents that were considered.
    """
    raise NotImplementedError
