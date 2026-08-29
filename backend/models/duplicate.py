"""The DuplicateDecision model: whether a report describes a known incident.

Deduplication is the judgment Relay is least able to take back. Merging two
genuinely different problems hides one of them until someone notices the work
order does not match the complaint; splitting one problem into five incidents
sends five crews. The third verdict, ``needs_review``, exists so the model can
decline rather than guess.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from models.common import RelayModel

MAX_REASONING_LENGTH = 1000


class DuplicateVerdict(StrEnum):
    """Outcome of comparing a report against candidate incidents."""

    SAME_INCIDENT = "same_incident"
    DIFFERENT_INCIDENT = "different_incident"
    NEEDS_REVIEW = "needs_review"


class DuplicateDecision(RelayModel):
    """Structured output of :func:`tools.find_duplicate_incident.compare_incidents`.

    ``reasoning`` is written for a facilities manager reading the incident
    history, not for a developer reading logs: it is the record of why two
    reports were treated as one problem, and has to stand on its own months
    later.
    """

    decision: DuplicateVerdict = Field(
        description="Whether the report matches a candidate incident."
    )
    matched_incident_id: str | None = Field(
        default=None,
        description="Incident the report belongs to; set only for "
        "``same_incident``.",
    )
    reasoning: str = Field(
        default="",
        description="Plain-language explanation of the decision, suitable for "
        "the incident's audit trail.",
    )

    @model_validator(mode="after")
    def _clear_unmatched_id(self) -> "DuplicateDecision":
        """Drop a match id on any verdict other than ``same_incident``.

        A model that answers ``different_incident`` while still naming an
        incident is contradicting itself. Keeping the id would let a caller
        that reads the id without checking the verdict merge the report anyway.
        """
        if self.decision is not DuplicateVerdict.SAME_INCIDENT:
            object.__setattr__(self, "matched_incident_id", None)
        object.__setattr__(
            self, "reasoning", self.reasoning.strip()[:MAX_REASONING_LENGTH]
        )
        return self
