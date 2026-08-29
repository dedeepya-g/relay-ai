"""Wire contracts for the Relay API.

Separate from the models in ``models/``: those describe what Relay stores, and
these describe what it accepts and returns. Keeping them apart means a
Firestore field can be renamed without silently changing the public API, and a
response can omit internal state without stripping fields from a stored model.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.common import (
    IncidentStatus,
    IssueCategory,
    Priority,
    ReportStatus,
    RoomType,
)


class RelaySchema(BaseModel):
    """Base for every wire schema."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReportIntakeResponse(RelaySchema):
    """What the caller learns from submitting one report.

    Reports the whole pipeline outcome in one payload, because a reporter
    submitting a duplicate should immediately see that it joined an existing
    incident rather than being told only that their report was received.
    """

    report_id: str
    outcome: str = Field(
        description="One of 'new_incident', 'merged', or 'needs_review'."
    )
    incident_id: str | None = Field(
        default=None,
        description="Incident the report belongs to; null when the report is "
        "awaiting human review and has deliberately not been linked.",
    )
    report_status: ReportStatus
    issue_type: IssueCategory | None = None
    is_potential_emergency: bool = False
    severity_signals: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    priority: Priority | None = Field(
        default=None, description="Null while a report awaits review."
    )
    team_assigned: str | None = None
    team_name: str | None = None
    sla_due_at: datetime | None = None
    evidence_count: int | None = Field(
        default=None, description="Reports linked to the incident after this one."
    )
    reasoning: dict[str, str] = Field(
        default_factory=dict,
        description="Explanation from each stage that made a judgment, keyed by "
        "stage: triage, deduplication, prioritization, routing.",
    )
    coordinator_actions: list[str] = Field(
        default_factory=list,
        description="Follow-up actions the incident coordinator took after the "
        "pipeline finished; empty when it judged none were needed.",
    )
    coordinator_reasoning: str | None = Field(
        default=None,
        description="The coordinator's own explanation of what it decided.",
    )
    work_order_ticket: str | None = Field(
        default=None,
        description="Dispatch ticket raised for the owning team; null while a "
        "report awaits review and has no incident to dispatch.",
    )
    photo_received: bool = Field(
        default=False,
        description="Whether a photo was uploaded with this report.",
    )
    photo_stored: bool = Field(
        default=False,
        description="Whether it was persisted. Always false for now: photo "
        "storage is not implemented, so an uploaded photo is acknowledged and "
        "discarded rather than silently appearing to have been kept.",
    )


class IncidentSummary(RelaySchema):
    """One incident as it appears in a list."""

    incident_id: str
    title: str
    category: IssueCategory
    priority: Priority
    status: IncidentStatus
    building_id: str
    floor: str | None = None
    room: str | None = None
    assigned_team_id: str | None = None
    assigned_team_name: str | None = Field(
        default=None,
        description="Display name of the owning team, resolved from the campus "
        "configuration so callers never have to map team ids themselves.",
    )
    report_count: int
    escalation_level: int = Field(
        default=0,
        description="How many times the overdue sweep has raised this "
        "incident; 0 means never escalated.",
    )
    sla_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IncidentList(RelaySchema):
    """A page of incidents."""

    incidents: list[IncidentSummary]
    count: int


class LinkedReport(RelaySchema):
    """One report merged into an incident, as evidence."""

    report_id: str
    description: str
    status: ReportStatus
    floor: str | None = None
    room: str | None = None
    is_potential_emergency: bool = False
    severity_signals: list[str] = Field(default_factory=list)
    submitted_at: datetime


class DecisionEntry(RelaySchema):
    """One entry in an incident's reasoning trail."""

    decision_id: str
    decision_type: str
    decided_by: str = Field(
        description="What executed the decision: 'model' for a language-model "
        "judgment, 'rule' for deterministic policy, 'agent' for the "
        "coordinating agent, or 'human' for a person.",
    )
    subject_id: str
    outcome: str
    rationale: str
    model: str | None = Field(
        default=None,
        description="Model that produced the judgment; null for decisions made "
        "by rule rather than by the model.",
    )
    created_at: datetime


class IncidentDetail(RelaySchema):
    """One incident with its evidence and its reasoning trail."""

    incident: IncidentSummary
    summary: str
    reports: list[LinkedReport]
    decisions: list[DecisionEntry]


class ResolveReviewRequest(RelaySchema):
    """A person's decision about a report Relay declined to place."""

    resolution: str = Field(
        description="'same_incident' or 'different_incident'."
    )
    incident_id: str | None = Field(
        default=None,
        description="Incident to merge into; required for 'same_incident'.",
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Reviewer's explanation, recorded in the audit trail in "
        "place of the default rationale.",
    )


class ResolveReviewResponse(RelaySchema):
    """Where a resolved report ended up."""

    report_id: str
    outcome: str = Field(description="'merged' or 'new_incident'.")
    incident_id: str
    resolved_by: str = Field(description="Always 'human' for this endpoint.")


# --- Campus reference data --------------------------------------------------


class RoomOption(RelaySchema):
    """One room a reporter can select."""

    number: str
    floor: str
    room_type: RoomType
    name: str | None = None


class BuildingOption(RelaySchema):
    """One building, with the floors and rooms a reporter can select."""

    building_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    floors: list[str] = Field(default_factory=list)
    rooms: list[RoomOption] = Field(default_factory=list)


class TeamOption(RelaySchema):
    """One maintenance team, and what it owns."""

    team_id: str
    name: str
    categories: list[IssueCategory] = Field(default_factory=list)
    coverage_hours: str


class CampusResponse(RelaySchema):
    """Reference data a client needs to submit a report and label a queue.

    Served from the seeded campus configuration rather than duplicated in the
    client, so the locations a reporter can choose are exactly the locations
    routing and deduplication know about.
    """

    campus_id: str
    name: str
    timezone: str
    buildings: list[BuildingOption]
    teams: list[TeamOption]
    sla_minutes: dict[Priority, int]


class PendingReview(RelaySchema):
    """A report Relay declined to place, awaiting a person."""

    report_id: str
    description: str
    building_id: str
    floor: str | None = None
    room: str | None = None
    issue_type: IssueCategory | None = None
    is_potential_emergency: bool = False
    severity_signals: list[str] = Field(default_factory=list)
    reasoning: str = Field(
        default="",
        description="Why Relay could not place this report, from the "
        "deduplication decision that paused it.",
    )
    submitted_at: datetime


class PendingReviewList(RelaySchema):
    """Everything currently waiting on a human decision."""

    reports: list[PendingReview]
    count: int


# --- Overdue sweep ----------------------------------------------------------


class EscalationEntry(RelaySchema):
    """One incident raised by the overdue sweep."""

    incident_id: str
    title: str
    escalation_level: int
    minutes_past_deadline: int
    supporting_team_id: str | None = None
    supporting_ticket: str | None = None
    work_order_tickets: list[str] = Field(default_factory=list)


class OverdueSweepResponse(RelaySchema):
    """Outcome of one pass of the overdue sweep."""

    campus_id: str
    checked_count: int = Field(description="Incidents found past their deadline.")
    escalated_count: int = Field(
        description="Of those, how many the escalation policy actually raised. "
        "The two differ when an incident is inside its grace period, inside "
        "the repeat interval, or already at the policy's maximum level."
    )
    escalations: list[EscalationEntry] = Field(default_factory=list)
