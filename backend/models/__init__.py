"""Pydantic models for every document Relay persists in Firestore."""

from models.campus_config import (
    Building,
    CampusConfig,
    EscalationPolicy,
    MaintenanceTeam,
)
from models.common import (
    DecisionType,
    IncidentStatus,
    IssueCategory,
    Location,
    Priority,
    RelayModel,
    ReportSource,
    ReportStatus,
    WorkOrderStatus,
    new_id,
    utc_now,
)
from models.decision import Decision
from models.incident import Incident
from models.report import Report
from models.work_order import WorkOrder

__all__ = [
    "Building",
    "CampusConfig",
    "Decision",
    "DecisionType",
    "EscalationPolicy",
    "Incident",
    "IncidentStatus",
    "IssueCategory",
    "Location",
    "MaintenanceTeam",
    "Priority",
    "RelayModel",
    "Report",
    "ReportSource",
    "ReportStatus",
    "WorkOrder",
    "WorkOrderStatus",
    "new_id",
    "utc_now",
]
