"""The WorkOrder model: the dispatch record sent to a maintenance team."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import (
    Priority,
    RelayModel,
    WorkOrderStatus,
    new_id,
    utc_now,
)


class WorkOrder(RelayModel):
    """An actionable assignment issued to one team for one incident.

    An incident normally has a single open work order. A second one is created
    when work is handed to a different team -- for example when electrical
    finds that the root cause is a roof leak and plumbing has to go first.
    """

    id: str = Field(default_factory=lambda: new_id("wo"))
    campus_id: str = Field(description="Campus this work order belongs to.")
    incident_id: str = Field(description="Incident this work order resolves.")

    # --- Assignment ---------------------------------------------------------
    team_id: str = Field(description="Maintenance team the work is dispatched to.")
    assignee: str | None = Field(
        default=None, description="Technician name, once the team assigns one."
    )
    priority: Priority = Field(
        description="Copied from the incident at dispatch time."
    )
    instructions: str = Field(
        max_length=2000,
        description="What the technician should do, written for the field.",
    )

    # --- Progress -----------------------------------------------------------
    status: WorkOrderStatus = Field(default=WorkOrderStatus.PENDING)
    due_at: datetime | None = Field(
        default=None, description="Deadline inherited from the incident SLA."
    )
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    completion_notes: str | None = Field(
        default=None, max_length=2000, description="What the technician did."
    )
    cancellation_reason: str | None = Field(
        default=None,
        max_length=500,
        description="Why the work order was cancelled, if it was.",
    )

    # --- Timestamps ---------------------------------------------------------
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
