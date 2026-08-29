"""ADK tool: apply a person's decision to a report paused for review.

Closes the loop that :func:`tools.find_duplicate_incident.find_duplicate_incident`
opens. When deduplication declines to guess, the report waits in
``pending_review``; this is the only way out of that state, and it exists so a
paused report is genuinely awaiting a decision rather than stranded.

The judgment here is a person's, so the Decision it records is attributed to a
human. That distinction is the point: an operator auditing an incident should
be able to see which links Relay made on its own and which a person confirmed.
"""

from __future__ import annotations

import logging
from typing import Any

from models.common import DecisionActor, DecisionType, ReportStatus
from models.decision import Decision
from models.duplicate import DuplicateVerdict
from models.report import Report
from services.firestore_service import get_report, record_decision
from tools.merge_report_into_incident import merge_report_into_incident
from tools.open_incident import open_incident

logger = logging.getLogger(__name__)

#: Verdicts a person may resolve a paused report to. ``needs_review`` is not
#: among them: re-declining would leave the report exactly where it is.
RESOLUTIONS = frozenset(
    {DuplicateVerdict.SAME_INCIDENT, DuplicateVerdict.DIFFERENT_INCIDENT}
)


def _record(
    report: Report, outcome: str, resolution: str, note: str | None
) -> None:
    """Record the human resolution alongside the agent's original decision.

    Appended rather than replacing the ``needs_review`` decision already on
    file, so the trail shows both that Relay declined and how a person settled
    it.
    """
    record_decision(
        Decision(
            campus_id=report.campus_id,
            decision_type=DecisionType.DEDUPLICATION,
            decided_by=DecisionActor.HUMAN,
            subject_type="reports",
            subject_id=report.id,
            outcome=outcome,
            rationale=note
            or f"A reviewer resolved this report as {resolution} after Relay "
            "declined to decide automatically.",
            tool_name="resolve_review",
            model=None,
            inputs={"resolution": resolution},
        )
    )


def resolve_review(
    report_id: str,
    resolution: str,
    incident_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Apply a person's decision to a report awaiting review.

    Call this when a reviewer has looked at a report Relay paused and decided
    where it belongs. Takes the same actions automatic deduplication would have
    taken, so a resolved report is indistinguishable from one placed
    automatically except in the audit trail.

    Args:
        report_id: Id of the paused report.
        resolution: ``same_incident`` or ``different_incident``.
        incident_id: Incident to merge into; required for ``same_incident``.
        note: Reviewer's own explanation, recorded in place of the default
            rationale.

    Returns:
        A dict with ``outcome`` (``merged`` or ``new_incident``),
        ``report_id``, ``incident_id``, and ``resolved_by``; or
        ``{"error": ...}`` if the report is not awaiting review or the
        resolution is unusable.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id!r}."}
    if report.status is not ReportStatus.PENDING_REVIEW:
        return {
            "error": f"Report {report_id!r} is {report.status.value}, not "
            "awaiting review; there is nothing to resolve."
        }

    try:
        verdict = DuplicateVerdict(resolution)
    except ValueError:
        return {
            "error": f"Unknown resolution {resolution!r}; expected one of "
            f"{sorted(v.value for v in RESOLUTIONS)}."
        }
    if verdict not in RESOLUTIONS:
        return {
            "error": f"Resolution {resolution!r} would leave the report "
            "awaiting review; expected one of "
            f"{sorted(v.value for v in RESOLUTIONS)}."
        }

    if verdict is DuplicateVerdict.SAME_INCIDENT:
        if not incident_id:
            return {
                "error": "Resolving as same_incident requires the incident_id "
                "to merge into."
            }
        merged = merge_report_into_incident(report_id, incident_id)
        if "error" in merged:
            return merged
        _record(report, f"merged into {incident_id}", resolution, note)
        return {
            "outcome": "merged",
            "report_id": report_id,
            "incident_id": incident_id,
            "report_count": merged["report_count"],
            "resolved_by": DecisionActor.HUMAN.value,
        }

    opened = open_incident(report_id)
    if "error" in opened:
        return opened
    _record(report, f"opened {opened['incident_id']}", resolution, note)
    return {
        "outcome": "new_incident",
        "report_id": report_id,
        "incident_id": opened["incident_id"],
        "title": opened["title"],
        "resolved_by": DecisionActor.HUMAN.value,
    }
