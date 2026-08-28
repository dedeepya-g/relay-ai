"""The Report model: one submission from one person about one observation."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import (
    IssueCategory,
    Location,
    RelayModel,
    ReportSource,
    ReportStatus,
    new_id,
    utc_now,
)


class Report(RelayModel):
    """A single facility report submitted to Relay.

    A report is immutable evidence: Relay never rewrites what a reporter said.
    Triage results are added alongside the original text, and the report is
    linked to exactly one :class:`~models.incident.Incident` once Relay decides
    whether it describes a new problem or an already-known one.
    """

    id: str = Field(default_factory=lambda: new_id("rpt"))
    campus_id: str = Field(description="Campus this report belongs to.")

    # --- What the reporter submitted ---------------------------------------
    source: ReportSource = Field(
        default=ReportSource.WEB, description="Channel the report arrived through."
    )
    description: str = Field(
        min_length=1,
        max_length=4000,
        description="Reporter's own description of the problem.",
    )
    location: Location = Field(description="Where the issue was observed.")
    photo_uri: str | None = Field(
        default=None,
        description="``gs://`` URI of the uploaded photo, if one was attached.",
    )
    reporter_name: str | None = Field(
        default=None, description="Reporter's name; omitted for anonymous reports."
    )
    reporter_email: str | None = Field(
        default=None, description="Contact address for resolution updates."
    )

    # --- What Relay inferred ------------------------------------------------
    status: ReportStatus = Field(default=ReportStatus.RECEIVED)
    incident_id: str | None = Field(
        default=None,
        description="Incident this report was merged into, once triaged.",
    )
    category: IssueCategory | None = Field(
        default=None, description="Category inferred during triage."
    )
    summary: str | None = Field(
        default=None,
        max_length=500,
        description="One-line normalized summary produced during triage.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Salient terms extracted during triage, used to match duplicates.",
    )

    # --- Timestamps ---------------------------------------------------------
    submitted_at: datetime = Field(default_factory=utc_now)
    triaged_at: datetime | None = Field(
        default=None, description="When triage finished; ``None`` while queued."
    )
