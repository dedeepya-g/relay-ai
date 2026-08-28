"""The Decision model: an audit record of one choice Relay made."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from models.common import DecisionType, RelayModel, new_id, utc_now


class Decision(RelayModel):
    """One agent decision, recorded so a human can audit or reverse it.

    Every consequential action -- merging two reports, raising a priority,
    routing to a team, escalating an overdue incident -- writes a decision.
    Together they form the explanation Relay shows operators when they ask why
    an incident looks the way it does.
    """

    id: str = Field(default_factory=lambda: new_id("dec"))
    campus_id: str = Field(description="Campus this decision belongs to.")

    # --- What was decided ---------------------------------------------------
    decision_type: DecisionType
    subject_type: str = Field(
        description="Collection the decision applies to, e.g. 'incidents'."
    )
    subject_id: str = Field(description="Id of the report or incident affected.")
    outcome: str = Field(
        max_length=500,
        description="The decision itself, e.g. 'merged into inc_9f2c1a4be80d'.",
    )
    rationale: str = Field(
        max_length=2000, description="Model-supplied reasoning for the outcome."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence; ``None`` for deterministic rule decisions.",
    )

    # --- How it was decided -------------------------------------------------
    tool_name: str | None = Field(
        default=None, description="ADK tool that produced the decision."
    )
    model: str | None = Field(
        default=None,
        description="Gemini model id used; ``None`` for rule-based decisions.",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Inputs the decision was based on, for replay and debugging.",
    )
    requires_review: bool = Field(
        default=False,
        description="Whether low confidence flagged this for human review.",
    )

    created_at: datetime = Field(default_factory=utc_now)
