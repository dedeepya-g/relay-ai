"""Shared enums, value objects, and the base model for Relay documents."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

_ID_LENGTH = 12


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Return a short, human-readable document id such as ``rpt_9f2c1a4be80d``.

    Args:
        prefix: Short document-type prefix, e.g. ``rpt`` or ``inc``.

    Returns:
        The prefix joined to a random hex suffix by an underscore.
    """
    return f"{prefix}_{uuid.uuid4().hex[:_ID_LENGTH]}"


class Priority(StrEnum):
    """Urgency assigned to an incident, driving SLA windows and escalation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueCategory(StrEnum):
    """Facility issue categories used for routing to maintenance teams."""

    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    ACCESS = "access"
    CUSTODIAL = "custodial"
    STRUCTURAL = "structural"
    SAFETY = "safety"
    GROUNDS = "grounds"
    IT_AV = "it_av"
    ELEVATOR = "elevator"
    PEST = "pest"
    OTHER = "other"


class RoomType(StrEnum):
    """How a room is used, which shapes both urgency and access constraints.

    A burst pipe in a lab threatens equipment, the same pipe in a corridor does
    not; a restroom fault is reported by many people at once, an office fault by
    one. Routing and deduplication both read this.
    """

    CLASSROOM = "classroom"
    OFFICE = "office"
    RESTROOM = "restroom"
    LAB = "lab"
    COMMON_AREA = "common_area"
    ELEVATOR_LOBBY = "elevator_lobby"


class ReportSource(StrEnum):
    """Channel a facility report arrived through."""

    WEB = "web"
    MOBILE = "mobile"
    EMAIL = "email"
    KIOSK = "kiosk"
    VOICE = "voice"


class ReportStatus(StrEnum):
    """Lifecycle of a single submitted report."""

    RECEIVED = "received"
    TRIAGED = "triaged"
    LINKED = "linked"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class IncidentStatus(StrEnum):
    """Lifecycle of an incident from intake through closure."""

    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


class WorkOrderStatus(StrEnum):
    """Lifecycle of a work order dispatched to a maintenance team."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionType(StrEnum):
    """Kinds of agent decisions recorded in the audit trail."""

    TRIAGE = "triage"
    DEDUPLICATION = "deduplication"
    PRIORITIZATION = "prioritization"
    ROUTING = "routing"
    ESCALATION = "escalation"
    RESOLUTION = "resolution"


class RelayModel(BaseModel):
    """Base model for every Relay document.

    Enforces strict validation so that a typo in a field name fails loudly
    rather than silently writing an unexpected shape into Firestore.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )

    def to_firestore(self) -> dict[str, Any]:
        """Return the document body to persist in Firestore.

        ``datetime`` values are kept native so Firestore stores them as
        timestamps, and ``StrEnum`` values serialize as their string value.
        """
        return self.model_dump(mode="python")

    @classmethod
    def from_firestore(cls, document_id: str, data: dict[str, Any]) -> Self:
        """Rebuild a model from a Firestore snapshot.

        Args:
            document_id: Firestore document id, used as the model's ``id``.
            data: Raw document body.

        Returns:
            The validated model instance.

        Raises:
            pydantic.ValidationError: If the stored document does not match the
                current schema.
        """
        return cls.model_validate({**data, "id": document_id})


class Location(RelayModel):
    """Where on campus an issue was observed."""

    building_id: str = Field(description="Building id from the campus config.")
    building_name: str | None = Field(
        default=None, description="Human-readable building name, for display."
    )
    floor: str | None = Field(default=None, description="Floor label, e.g. '3' or 'B1'.")
    room: str | None = Field(default=None, description="Room or suite number.")
    detail: str | None = Field(
        default=None,
        description="Free-text refinement, e.g. 'second stall from the window'.",
    )
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
