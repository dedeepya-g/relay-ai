"""ADK tool: open a new incident from a report."""

from __future__ import annotations

import logging
from typing import Any

from models.common import IssueCategory, ReportStatus
from models.incident import Incident
from models.report import Report
from services.firestore_service import (
    create_incident,
    get_campus_config,
    get_report,
    update_report,
)

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 140

#: Categories whose display form is not just the value title-cased. Everything
#: else falls through to .title(), which handles the ordinary trades.
CATEGORY_LABELS = {
    IssueCategory.HVAC: "HVAC",
    IssueCategory.IT_AV: "IT/AV",
}


def _building_name(campus_id: str, building_id: str) -> str:
    """Resolve a building id to its official name for display.

    Falls back to the id when the campus is unseeded or the building is
    unknown. A crew reading a work order should see "Harlow Science Center",
    not "bldg_harlow_science", but a missing name is not worth failing over.
    """
    config = get_campus_config(campus_id)
    if config is not None:
        for building in config.buildings:
            if building.id == building_id:
                return building.name
    return building_id


def _build_title(report: Report) -> str:
    """Compose a dispatch-ready title from the report's category and location.

    Deterministic on purpose. A title is what a crew reads on a work order, so
    it should say the same thing every time for the same report rather than
    varying with a model call, and it must not add detail the reporter did not
    give.
    """
    location = report.location
    where = location.building_name or _building_name(report.campus_id, location.building_id)
    if location.room:
        where = f"{where}, room {location.room}"
    elif location.floor:
        where = f"{where}, floor {location.floor}"

    category = (
        CATEGORY_LABELS.get(report.category, report.category.value.title())
        if report.category
        else "Facility"
    )
    return f"{category} issue - {where}"[:MAX_TITLE_LENGTH]


def open_incident(report_id: str) -> dict[str, Any]:
    """Open a new incident for a report that is not a duplicate.

    Call this only when ``find_duplicate_incident`` found no match. Creates the
    incident from the report's triage result, links the report to it, and marks
    the report as triaged.

    Args:
        report_id: Id of the report opening the incident.

    Returns:
        A dict with ``incident_id``, ``title``, ``category``, and ``status``;
        or ``{"error": ...}`` if the report is missing, untriaged, or already
        linked.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id!r}."}
    if report.category is None:
        return {"error": f"Report {report_id!r} has not been triaged yet."}
    if report.incident_id is not None:
        return {
            "error": f"Report {report_id!r} is already linked to incident "
            f"{report.incident_id!r}."
        }

    incident = create_incident(
        Incident(
            campus_id=report.campus_id,
            title=_build_title(report),
            summary=report.description,
            category=report.category,
            location=report.location,
            report_ids=[report.id],
            primary_report_id=report.id,
            photo_uris=[report.photo_uri] if report.photo_uri else [],
        )
    )
    update_report(
        report_id,
        {"incident_id": incident.id, "status": ReportStatus.LINKED.value},
    )

    return {
        "incident_id": incident.id,
        "title": incident.title,
        "category": incident.category.value,
        "status": incident.status.value,
    }
