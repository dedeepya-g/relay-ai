"""ADK tool: understand a raw facility report."""

from __future__ import annotations

from typing import Any


def triage_report(report_id: str) -> dict[str, Any]:
    """Read a facility report and extract what it is actually about.

    Call this first for every new report, before looking for duplicates.
    Combines the reporter's text with the attached photo, if any, to produce a
    normalized summary, an issue category, a resolved campus location, and the
    keywords later used to match duplicates.

    Args:
        report_id: Id of the report to triage.

    Returns:
        A dict with keys ``report_id``, ``summary``, ``category``,
        ``location``, ``keywords``, ``severity_signals``, and ``confidence``;
        or ``{"error": ...}`` if the report does not exist.
    """
    raise NotImplementedError
