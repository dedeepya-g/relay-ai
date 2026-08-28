"""The CampusConfig model: the policy Relay applies for one campus."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from models.common import IssueCategory, Priority, RelayModel, utc_now


class Building(RelayModel):
    """A building on campus that reports can refer to."""

    id: str = Field(description="Stable building id, e.g. 'bldg_science_hall'.")
    name: str = Field(description="Official building name.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Names people actually use, e.g. 'Sci Hall', used to "
        "resolve free-text locations onto this building.",
    )
    floors: list[str] = Field(
        default_factory=list, description="Floor labels, e.g. ['B1', '1', '2']."
    )


class MaintenanceTeam(RelayModel):
    """A team that work orders can be routed to."""

    id: str = Field(description="Stable team id, e.g. 'team_plumbing'.")
    name: str = Field(description="Team name shown in the dashboard.")
    categories: list[IssueCategory] = Field(
        description="Issue categories this team owns."
    )
    contact_email: str | None = None
    contact_phone: str | None = None
    coverage_hours: str = Field(
        default="24/7",
        description="Human-readable coverage window, e.g. 'Mon-Fri 07:00-17:00'.",
    )
    escalation_contact: str | None = Field(
        default=None,
        description="Supervisor notified when this team's work goes overdue.",
    )


class EscalationPolicy(RelayModel):
    """How Relay reacts when an incident misses its SLA deadline."""

    grace_period_minutes: int = Field(
        default=15,
        ge=0,
        description="Slack after the SLA deadline before the first escalation.",
    )
    repeat_interval_minutes: int = Field(
        default=60,
        gt=0,
        description="Interval between successive escalations while still overdue.",
    )
    max_level: int = Field(
        default=3, ge=1, description="Escalation level at which Relay stops raising."
    )
    notify_on_escalation: list[str] = Field(
        default_factory=list,
        description="Addresses notified at every escalation level.",
    )


class CampusConfig(RelayModel):
    """Per-campus configuration driving routing, SLAs, and escalation.

    Seeded once per campus by ``scripts/seed_campus_config.py`` and read by the
    agent tools at decision time, so policy can change without a redeploy.
    """

    id: str = Field(description="Campus id; also the Firestore document id.")
    name: str = Field(description="Campus display name, e.g. 'Relay University'.")
    timezone: str = Field(
        default="America/Los_Angeles",
        description="IANA timezone used for coverage windows and reporting.",
    )
    buildings: list[Building] = Field(default_factory=list)
    teams: list[MaintenanceTeam] = Field(default_factory=list)
    sla_hours: dict[Priority, float] = Field(
        description="Hours allowed to resolve an incident, keyed by priority."
    )
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    default_team_id: str | None = Field(
        default=None,
        description="Team receiving incidents whose category has no owner.",
    )
    updated_at: datetime = Field(default_factory=utc_now)
