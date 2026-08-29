"""Firestore read and write helpers for Relay documents.

This module is the only place that knows collection names and query shapes.
Agent tools and API routes call these helpers so persistence stays swappable
and every write goes through one validated path.
"""

from __future__ import annotations

import logging
from datetime import datetime

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from config import get_firestore_client
from models.campus_config import CampusConfig
from models.common import IncidentStatus, ReportStatus, utc_now
from models.decision import Decision
from models.incident import Incident
from models.report import Report
from models.work_order import WorkOrder

logger = logging.getLogger(__name__)

REPORTS_COLLECTION = "reports"
INCIDENTS_COLLECTION = "incidents"
WORK_ORDERS_COLLECTION = "work_orders"
DECISIONS_COLLECTION = "decisions"
CAMPUS_CONFIGS_COLLECTION = "campus_configs"

#: Statuses in which an incident is still live work and can absorb a duplicate
#: report. A resolved or closed incident should not swallow a new report: if the
#: problem recurred, that is a new incident with its own SLA.
ACTIVE_INCIDENT_STATUSES = frozenset(
    {
        IncidentStatus.OPEN,
        IncidentStatus.ASSIGNED,
        IncidentStatus.IN_PROGRESS,
        IncidentStatus.ON_HOLD,
        IncidentStatus.ESCALATED,
    }
)

#: Upper bound on documents pulled per deduplication sweep. Status and recency
#: are filtered in Python rather than in the query so that the read needs only
#: two equality filters and no composite index; this caps the cost of that
#: choice. A building with more live incidents than this is past the point
#: where automatic deduplication should be trusted anyway.
CANDIDATE_FETCH_LIMIT = 200


def _collection(name: str) -> firestore.CollectionReference:
    """Return a reference to a top-level collection on the cached client."""
    return get_firestore_client().collection(name)


# --- Reports ----------------------------------------------------------------


def create_report(report: Report) -> Report:
    """Persist a newly submitted report.

    Args:
        report: Validated report to write; its ``id`` becomes the document id.

    Returns:
        The stored report.
    """
    _collection(REPORTS_COLLECTION).document(report.id).set(report.to_firestore())
    logger.info("Created report %s for campus %s", report.id, report.campus_id)
    return report


def get_report(report_id: str) -> Report | None:
    """Fetch one report by id, or ``None`` if it does not exist."""
    snapshot = _collection(REPORTS_COLLECTION).document(report_id).get()
    if not snapshot.exists:
        return None
    return Report.from_firestore(snapshot.id, snapshot.to_dict())


def update_report(report_id: str, fields: dict[str, object]) -> Report:
    """Apply a partial update to a report and return the stored result.

    Args:
        report_id: Report to update.
        fields: Field paths to values, e.g. ``{"status": ReportStatus.TRIAGED}``.

    Returns:
        The report as stored after the update.

    Raises:
        KeyError: If the report does not exist.
    """
    document = _collection(REPORTS_COLLECTION).document(report_id)
    if not document.get().exists:
        raise KeyError(f"No report {report_id!r}.")
    document.update(fields)
    snapshot = document.get()
    return Report.from_firestore(snapshot.id, snapshot.to_dict())


def list_reports_by_status(
    campus_id: str, status: ReportStatus, limit: int = 100
) -> list[Report]:
    """Return reports in one lifecycle state, newest submission first.

    Used for the human-review queue: reports Relay declined to place are not
    attached to any incident, so they cannot be reached by walking incidents.

    Args:
        campus_id: Campus to scope the query to.
        status: Lifecycle state to match.
        limit: Maximum number of reports to return.
    """
    query = (
        _collection(REPORTS_COLLECTION)
        .where(filter=FieldFilter("campus_id", "==", campus_id))
        .where(filter=FieldFilter("status", "==", status.value))
        .limit(limit)
    )
    reports = [
        Report.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    reports.sort(key=lambda report: report.submitted_at, reverse=True)
    return reports


def list_reports_for_incident(incident_id: str) -> list[Report]:
    """Return every report merged into an incident, oldest submission first."""
    query = _collection(REPORTS_COLLECTION).where(
        filter=FieldFilter("incident_id", "==", incident_id)
    )
    reports = [
        Report.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    reports.sort(key=lambda report: report.submitted_at)
    return reports


# --- Incidents --------------------------------------------------------------


def create_incident(incident: Incident) -> Incident:
    """Persist a new incident opened from a report."""
    _collection(INCIDENTS_COLLECTION).document(incident.id).set(
        incident.to_firestore()
    )
    logger.info(
        "Opened incident %s (%s) in %s",
        incident.id,
        incident.category.value,
        incident.location.building_id,
    )
    return incident


def get_incident(incident_id: str) -> Incident | None:
    """Fetch one incident by id, or ``None`` if it does not exist."""
    snapshot = _collection(INCIDENTS_COLLECTION).document(incident_id).get()
    if not snapshot.exists:
        return None
    return Incident.from_firestore(snapshot.id, snapshot.to_dict())


def update_incident(incident_id: str, fields: dict[str, object]) -> Incident:
    """Apply a partial update to an incident, refreshing ``updated_at``.

    Args:
        incident_id: Incident to update.
        fields: Field paths to values.

    Returns:
        The incident as stored after the update.

    Raises:
        KeyError: If the incident does not exist.
    """
    document = _collection(INCIDENTS_COLLECTION).document(incident_id)
    if not document.get().exists:
        raise KeyError(f"No incident {incident_id!r}.")
    document.update({**fields, "updated_at": utc_now()})
    snapshot = document.get()
    return Incident.from_firestore(snapshot.id, snapshot.to_dict())


def list_open_incidents(campus_id: str, limit: int = 100) -> list[Incident]:
    """Return incidents that are not yet resolved or closed, newest first.

    Args:
        campus_id: Campus to scope the query to.
        limit: Maximum number of incidents to return.

    Returns:
        Live incidents, newest first.
    """
    query = (
        _collection(INCIDENTS_COLLECTION)
        .where(filter=FieldFilter("campus_id", "==", campus_id))
        .limit(CANDIDATE_FETCH_LIMIT)
    )
    incidents = [
        Incident.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    live = [
        incident
        for incident in incidents
        if incident.status in ACTIVE_INCIDENT_STATUSES
    ]
    live.sort(key=lambda incident: incident.created_at, reverse=True)
    return live[:limit]


def list_deduplication_candidates(
    campus_id: str,
    building_id: str,
    since: datetime,
    limit: int = 20,
) -> list[Incident]:
    """Return recent open incidents a new report might be a duplicate of.

    Narrows the search space before the model compares descriptions: only
    incidents in the same building that are still open and were created after
    ``since`` are worth comparing.

    Args:
        campus_id: Campus to scope the query to.
        building_id: Building the new report points at.
        since: Earliest incident creation time to consider.
        limit: Maximum number of candidates to return.

    Returns:
        Live incidents in the building created at or after ``since``, newest
        first.
    """
    query = (
        _collection(INCIDENTS_COLLECTION)
        .where(filter=FieldFilter("campus_id", "==", campus_id))
        .where(filter=FieldFilter("location.building_id", "==", building_id))
        .limit(CANDIDATE_FETCH_LIMIT)
    )
    incidents = [
        Incident.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    live = [
        incident
        for incident in incidents
        if incident.status in ACTIVE_INCIDENT_STATUSES and incident.created_at >= since
    ]
    live.sort(key=lambda incident: incident.created_at, reverse=True)
    return live[:limit]


def list_overdue_incidents(campus_id: str, as_of: datetime) -> list[Incident]:
    """Return unresolved incidents whose SLA deadline has passed.

    Args:
        campus_id: Campus to scope the query to.
        as_of: Time to evaluate the deadline against, normally now.

    Returns:
        Live incidents whose deadline has passed, longest overdue first.
        Already-escalated incidents are included: an incident that stays
        unresolved should keep climbing, and whether it may is the escalation
        policy's decision through its repeat interval and maximum level, not
        this query's. Excluding them here would silently cap every incident at
        level one and make that policy unreachable.
    """
    query = (
        _collection(INCIDENTS_COLLECTION)
        .where(filter=FieldFilter("campus_id", "==", campus_id))
        .limit(CANDIDATE_FETCH_LIMIT)
    )
    incidents = [
        Incident.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    overdue = [
        incident
        for incident in incidents
        if incident.status in ACTIVE_INCIDENT_STATUSES
        and incident.sla_due_at is not None
        and incident.sla_due_at < as_of
    ]
    overdue.sort(key=lambda incident: incident.sla_due_at)
    return overdue


# --- Work orders ------------------------------------------------------------


def create_work_order(work_order: WorkOrder) -> WorkOrder:
    """Persist a work order dispatched to a maintenance team."""
    _collection(WORK_ORDERS_COLLECTION).document(work_order.id).set(
        work_order.to_firestore()
    )
    logger.info(
        "Dispatched work order %s (%s) to %s",
        work_order.ticket,
        work_order.id,
        work_order.team_id,
    )
    return work_order


def get_work_order(work_order_id: str) -> WorkOrder | None:
    """Fetch one work order by id, or ``None`` if it does not exist."""
    snapshot = _collection(WORK_ORDERS_COLLECTION).document(work_order_id).get()
    if not snapshot.exists:
        return None
    return WorkOrder.from_firestore(snapshot.id, snapshot.to_dict())


def update_work_order(work_order_id: str, fields: dict[str, object]) -> WorkOrder:
    """Apply a partial update to a work order, refreshing ``updated_at``.

    Raises:
        KeyError: If the work order does not exist.
    """
    document = _collection(WORK_ORDERS_COLLECTION).document(work_order_id)
    if not document.get().exists:
        raise KeyError(f"No work order {work_order_id!r}.")
    document.update({**fields, "updated_at": utc_now()})
    snapshot = document.get()
    return WorkOrder.from_firestore(snapshot.id, snapshot.to_dict())


def list_work_orders_for_incident(incident_id: str) -> list[WorkOrder]:
    """Return every work order raised for an incident, oldest first."""
    query = _collection(WORK_ORDERS_COLLECTION).where(
        filter=FieldFilter("incident_id", "==", incident_id)
    )
    work_orders = [
        WorkOrder.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    work_orders.sort(key=lambda work_order: work_order.created_at)
    return work_orders


# --- Decisions --------------------------------------------------------------


def record_decision(decision: Decision) -> Decision:
    """Append a decision to the audit trail.

    Decisions are append-only. Relay never rewrites one, because the record of
    what it decided at the time is the point.
    """
    _collection(DECISIONS_COLLECTION).document(decision.id).set(
        decision.to_firestore()
    )
    logger.info(
        "Recorded %s decision %s on %s",
        decision.decision_type.value,
        decision.id,
        decision.subject_id,
    )
    return decision


def list_decisions_for_subject(subject_id: str, limit: int = 50) -> list[Decision]:
    """Return decisions affecting one report or incident, newest first.

    Args:
        subject_id: Report or incident the decisions are about.
        limit: Maximum number of decisions to return.
    """
    query = _collection(DECISIONS_COLLECTION).where(
        filter=FieldFilter("subject_id", "==", subject_id)
    )
    decisions = [
        Decision.from_firestore(snapshot.id, snapshot.to_dict())
        for snapshot in query.stream()
    ]
    decisions.sort(key=lambda decision: decision.created_at, reverse=True)
    return decisions[:limit]


# --- Campus configuration ---------------------------------------------------


def get_campus_config(campus_id: str) -> CampusConfig | None:
    """Fetch a campus configuration, or ``None`` if it has not been seeded.

    Args:
        campus_id: Campus whose configuration to read.

    Returns:
        The validated configuration, or ``None`` if no document exists.

    Raises:
        pydantic.ValidationError: If a stored document no longer matches the
            current schema, which means the campus needs re-seeding rather than
            that it is unconfigured.
    """
    snapshot = _collection(CAMPUS_CONFIGS_COLLECTION).document(campus_id).get()
    if not snapshot.exists:
        return None
    return CampusConfig.from_firestore(snapshot.id, snapshot.to_dict())


def upsert_campus_config(config: CampusConfig) -> CampusConfig:
    """Create or replace a campus configuration document.

    The write replaces the document wholesale rather than merging, so a field
    removed from the configuration is removed from Firestore too and stale
    policy cannot survive a re-seed.

    Args:
        config: Configuration to store; its ``id`` becomes the document id.

    Returns:
        The stored configuration, with ``updated_at`` set to the write time.
    """
    stored = config.model_copy(update={"updated_at": utc_now()})
    _collection(CAMPUS_CONFIGS_COLLECTION).document(stored.id).set(
        stored.to_firestore()
    )
    logger.info("Wrote campus configuration %s", stored.id)
    return stored
