"""ADK tool: merge a duplicate report into an existing incident."""

from __future__ import annotations

import logging
from typing import Any

from models.common import ReportStatus
from services.firestore_service import (
    get_incident,
    get_report,
    update_incident,
    update_report,
)

logger = logging.getLogger(__name__)

MAX_SUMMARY_LENGTH = 2000


def _extend_summary(summary: str, description: str) -> str:
    """Append a corroborating report to the incident summary.

    Appends rather than rewrites: the original wording is evidence, and losing
    it to a paraphrase would weaken the record a facilities manager reads. The
    summary stops growing once it reaches the model's limit, at which point the
    linked reports remain the full record.
    """
    addition = f"Also reported: {description}"
    if addition in summary:
        return summary
    combined = f"{summary}\n{addition}"
    return combined if len(combined) <= MAX_SUMMARY_LENGTH else summary


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
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id!r}."}
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id!r}."}
    if report.incident_id is not None and report.incident_id != incident_id:
        return {
            "error": f"Report {report_id!r} is already linked to incident "
            f"{report.incident_id!r}."
        }

    report_ids = list(dict.fromkeys([*incident.report_ids, report_id]))
    photo_uris = list(
        dict.fromkeys(
            [*incident.photo_uris, *([report.photo_uri] if report.photo_uri else [])]
        )
    )
    updated = update_incident(
        incident_id,
        {
            "report_ids": report_ids,
            "photo_uris": photo_uris,
            "summary": _extend_summary(incident.summary, report.description),
        },
    )
    update_report(
        report_id,
        {"incident_id": incident_id, "status": ReportStatus.LINKED.value},
    )

    return {
        "incident_id": incident_id,
        "report_ids": updated.report_ids,
        "report_count": len(updated.report_ids),
        "summary": updated.summary,
    }
