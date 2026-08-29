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


def ticket_number(work_order_id: str) -> str:
    """Derive the short number a technician reads off a radio.

    Taken from the document id rather than a counter: a sequential number would
    need a transaction to stay unique, and nothing here benefits from work
    orders being consecutively numbered.
    """
    return f"WO-{work_order_id.rsplit('_', 1)[-1][:6].upper()}"


class StatusChange(RelayModel):
    """One transition in a work order's life.

    Kept as history rather than only a current status, because "when did the
    team actually get this?" is the question asked after a deadline is missed.
    """

    status: WorkOrderStatus
    at: datetime = Field(default_factory=utc_now)
    note: str | None = Field(
        default=None, max_length=500, description="Why the status changed."
    )


class WorkOrder(RelayModel):
    """An actionable assignment issued to one team for one incident.

    An incident normally has a single open work order. A second one is created
    when work is handed to a different team -- for example when electrical
    finds that the root cause is a roof leak and plumbing has to go first.
    """

    id: str = Field(default_factory=lambda: new_id("wo"))
    ticket: str = Field(
        description="Short human-facing dispatch number, e.g. 'WO-4BC910'."
    )
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
    status_history: list[StatusChange] = Field(
        default_factory=list,
        description="Every status this work order has held, oldest first.",
    )
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
