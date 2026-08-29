"""The TriageResult model: what Gemini extracts from a single report.

Triage is deliberately the narrowest step in the pipeline. It reads one report
and says what the report is about; it does not decide priority, team, or SLA.
Those depend on campus policy, which lives in
:class:`~models.campus_config.CampusConfig` and is applied downstream.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field, field_validator

from models.common import IssueCategory, RelayModel

logger = logging.getLogger(__name__)

MAX_SEVERITY_SIGNALS = 12
MAX_SIGNAL_LENGTH = 200
MAX_CONFIDENCE_NOTE_LENGTH = 400


class MissingField(StrEnum):
    """A detail triage wanted but could not obtain from report or photo.

    Constrained to a fixed set so downstream code can act on the values -- ask
    the reporter a follow-up question, or hold routing until a location is
    known -- rather than pattern-matching free text.

    Deliberately limited to location. A missing photo is not actionable for a
    dispatcher the way a missing room number is, and listing it on every
    text-only report would bury the gaps that can actually be closed.
    """

    BUILDING = "building"
    FLOOR = "floor"
    ROOM = "room"


class TriageResult(RelayModel):
    """Structured output of :func:`tools.triage_report.analyze_report`.

    Every field is an observation about the report, never a decision about what
    to do with it. ``is_potential_emergency`` is the one field that comes close,
    and it is still only a signal: it says the report describes conditions that
    look dangerous, not that the incident is critical priority.
    """

    issue_type: IssueCategory = Field(
        description="Category of the underlying fault, chosen from IssueCategory."
    )
    severity_signals: list[str] = Field(
        default_factory=list,
        description="Phrases from the report indicating urgency or escalation, "
        "quoted rather than paraphrased so the audit trail stays traceable to "
        "the reporter's own words.",
    )
    is_potential_emergency: bool = Field(
        default=False,
        description="Whether the report describes conditions posing genuine "
        "danger to people or rapidly worsening damage.",
    )
    missing_fields: list[MissingField] = Field(
        default_factory=list,
        description="Details that would improve routing but are absent from "
        "both the report and any attached photo.",
    )
    confidence_note: str = Field(
        default="",
        description="One sentence naming the uncertainty in this "
        "classification, or stating that the report was unambiguous.",
    )

    @field_validator("issue_type", mode="before")
    @classmethod
    def _coerce_unknown_category(cls, value: object) -> object:
        """Fall back to ``other`` when the model invents a category.

        The response schema constrains this field, so an unknown value should
        be unreachable. Treating it as data corruption rather than a crash
        keeps one malformed response from failing the whole report -- the
        report still gets classified, just conservatively.
        """
        if isinstance(value, IssueCategory) or not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if normalized in set(IssueCategory):
            return normalized
        logger.warning(
            "Gemini returned unknown issue_type %r; falling back to %r.",
            value,
            IssueCategory.OTHER.value,
        )
        return IssueCategory.OTHER

    @field_validator("severity_signals", mode="after")
    @classmethod
    def _clean_signals(cls, value: list[str]) -> list[str]:
        """Drop blanks, truncate, and de-duplicate while preserving order."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for signal in value:
            text = signal.strip()[:MAX_SIGNAL_LENGTH]
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                cleaned.append(text)
        return cleaned[:MAX_SEVERITY_SIGNALS]

    @field_validator("missing_fields", mode="after")
    @classmethod
    def _dedupe_missing_fields(cls, value: list[MissingField]) -> list[MissingField]:
        """Remove repeats while preserving the model's ordering."""
        return list(dict.fromkeys(value))

    @field_validator("confidence_note", mode="after")
    @classmethod
    def _truncate_note(cls, value: str) -> str:
        """Keep the note to one readable sentence's worth of text."""
        return value.strip()[:MAX_CONFIDENCE_NOTE_LENGTH]
