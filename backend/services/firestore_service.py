"""Firestore read and write helpers for Relay documents.

This module is the only place that knows collection names and query shapes.
Agent tools and API routes call these helpers so persistence stays swappable
and every write goes through one validated path.
"""

from __future__ import annotations

import logging
from datetime import datetime

from models.campus_config import CampusConfig
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


# --- Reports ----------------------------------------------------------------


def create_report(report: Report) -> Report:
    """Persist a newly submitted report.

    Args:
        report: Validated report to write; its ``id`` becomes the document id.

    Returns:
        The stored report.
    """
    raise NotImplementedError


def get_report(report_id: str) -> Report | None:
    """Fetch one report by id, or ``None`` if it does not exist."""
    raise NotImplementedError


def update_report(report_id: str, fields: dict[str, object]) -> Report:
    """Apply a partial update to a report and return the stored result.

    Args:
        report_id: Report to update.
        fields: Field paths to values, e.g. ``{"status": ReportStatus.TRIAGED}``.

    Raises:
        KeyError: If the report does not exist.
    """
    raise NotImplementedError


def list_reports_for_incident(incident_id: str) -> list[Report]:
    """Return every report merged into an incident, oldest submission first."""
    raise NotImplementedError


# --- Incidents --------------------------------------------------------------


def create_incident(incident: Incident) -> Incident:
    """Persist a new incident opened from a report."""
    raise NotImplementedError


def get_incident(incident_id: str) -> Incident | None:
    """Fetch one incident by id, or ``None`` if it does not exist."""
    raise NotImplementedError


def update_incident(incident_id: str, fields: dict[str, object]) -> Incident:
    """Apply a partial update to an incident, refreshing ``updated_at``.

    Raises:
        KeyError: If the incident does not exist.
    """
    raise NotImplementedError


def list_open_incidents(campus_id: str, limit: int = 100) -> list[Incident]:
    """Return incidents that are not yet resolved or closed, newest first.

    Args:
        campus_id: Campus to scope the query to.
        limit: Maximum number of incidents to return.
    """
    raise NotImplementedError


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
    """
    raise NotImplementedError


def list_overdue_incidents(campus_id: str, as_of: datetime) -> list[Incident]:
    """Return unresolved incidents whose SLA deadline has passed.

    Args:
        campus_id: Campus to scope the query to.
        as_of: Time to evaluate the deadline against, normally now.
    """
    raise NotImplementedError


# --- Work orders ------------------------------------------------------------


def create_work_order(work_order: WorkOrder) -> WorkOrder:
    """Persist a work order dispatched to a maintenance team."""
    raise NotImplementedError


def get_work_order(work_order_id: str) -> WorkOrder | None:
    """Fetch one work order by id, or ``None`` if it does not exist."""
    raise NotImplementedError


def update_work_order(work_order_id: str, fields: dict[str, object]) -> WorkOrder:
    """Apply a partial update to a work order, refreshing ``updated_at``.

    Raises:
        KeyError: If the work order does not exist.
    """
    raise NotImplementedError


def list_work_orders_for_incident(incident_id: str) -> list[WorkOrder]:
    """Return every work order raised for an incident, oldest first."""
    raise NotImplementedError


# --- Decisions --------------------------------------------------------------


def record_decision(decision: Decision) -> Decision:
    """Append a decision to the audit trail."""
    raise NotImplementedError


def list_decisions_for_subject(subject_id: str, limit: int = 50) -> list[Decision]:
    """Return decisions affecting one report or incident, newest first."""
    raise NotImplementedError


# --- Campus configuration ---------------------------------------------------


def get_campus_config(campus_id: str) -> CampusConfig | None:
    """Fetch a campus configuration, or ``None`` if it has not been seeded."""
    raise NotImplementedError


def upsert_campus_config(config: CampusConfig) -> CampusConfig:
    """Create or replace a campus configuration document."""
    raise NotImplementedError
