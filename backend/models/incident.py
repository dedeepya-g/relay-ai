"""The Incident model: one real-world problem, backed by one or more reports."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import (
    IncidentStatus,
    IssueCategory,
    Location,
    Priority,
    RelayModel,
    new_id,
    utc_now,
)


class Incident(RelayModel):
    """A deduplicated facility problem tracked through to resolution.

    When several reports describe the same underlying problem -- three students
    reporting the same flooded restroom -- Relay merges them into one incident.
    The incident carries the priority, the responsible team, the SLA deadline,
    and the escalation state; the reports remain as supporting evidence.
    """

    id: str = Field(default_factory=lambda: new_id("inc"))
    campus_id: str = Field(description="Campus this incident belongs to.")

    # --- Problem description ------------------------------------------------
    title: str = Field(
        max_length=140, description="Short dispatch-ready title for the problem."
    )
    summary: str = Field(
        max_length=2000,
        description="Consolidated description synthesized from all linked reports.",
    )
    category: IssueCategory
    location: Location

    # --- Evidence -----------------------------------------------------------
    report_ids: list[str] = Field(
        default_factory=list,
        description="Reports merged into this incident, oldest first.",
    )
    primary_report_id: str | None = Field(
        default=None, description="Report that opened the incident."
    )
    photo_uris: list[str] = Field(
        default_factory=list,
        description="Photos carried over from the linked reports.",
    )

    # --- Triage outcome -----------------------------------------------------
    priority: Priority = Field(default=Priority.MEDIUM)
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    assigned_team_id: str | None = Field(
        default=None, description="Maintenance team responsible for the fix."
    )
    work_order_ids: list[str] = Field(
        default_factory=list, description="Work orders dispatched for this incident."
    )

    # --- SLA and escalation -------------------------------------------------
    sla_due_at: datetime | None = Field(
        default=None,
        description="Deadline derived from priority and the campus SLA policy.",
    )
    escalation_level: int = Field(
        default=0,
        ge=0,
        description="0 = never escalated; each overdue sweep raises it by one.",
    )
    last_escalated_at: datetime | None = None

    # --- Resolution ---------------------------------------------------------
    resolution_notes: str | None = Field(
        default=None, max_length=2000, description="How the problem was resolved."
    )
    resolved_at: datetime | None = None
    closed_at: datetime | None = None

    # --- Timestamps ---------------------------------------------------------
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
