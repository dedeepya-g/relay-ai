"""The CampusConfig model: the policy Relay applies for one campus."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from models.common import IssueCategory, Priority, RelayModel, RoomType, utc_now


class Room(RelayModel):
    """A addressable space within a building.

    Rooms are the finest location grain Relay matches on. Two reports naming
    the same room are far likelier to describe one incident than two reports
    naming only the same building, so deduplication leans on this.
    """

    number: str = Field(description="Room number as posted on the door, e.g. '318'.")
    floor: str = Field(description="Floor label; must appear in the building's floors.")
    room_type: RoomType = Field(description="How the room is used.")
    name: str | None = Field(
        default=None,
        description="Display label for spaces people name rather than number, "
        "e.g. 'North Restroom' or 'Third Floor Elevator Lobby'.",
    )


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
    rooms: list[Room] = Field(
        default_factory=list,
        description="Known rooms, used to resolve free-text locations and to "
        "match reports at room granularity.",
    )

    @model_validator(mode="after")
    def _check_room_floors(self) -> "Building":
        """Reject rooms on floors the building does not have.

        A room whose floor is not in ``floors`` can never be matched by a
        location lookup, so it is a seeding bug rather than valid data.
        """
        unknown = sorted({room.floor for room in self.rooms} - set(self.floors))
        if unknown:
            raise ValueError(
                f"Building {self.id!r} has rooms on undeclared floors: "
                f"{', '.join(unknown)}."
            )
        return self


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
    sla_minutes: dict[Priority, int] = Field(
        description="Minutes allowed to resolve an incident, keyed by priority. "
        "Minutes rather than hours so a demo can watch an SLA breach and the "
        "resulting escalation happen live.",
    )
    emergency_keywords: list[str] = Field(
        default_factory=list,
        description="Lowercase phrases that force a report to critical priority "
        "regardless of model judgment, drawn from the emergency categories "
        "facilities departments call out explicitly.",
    )
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    default_team_id: str | None = Field(
        default=None,
        description="Team receiving incidents whose category has no owner.",
    )
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _check_references(self) -> "CampusConfig":
        """Reject a config whose internal references do not resolve.

        ``default_team_id`` pointing at a team that does not exist would strand
        every unowned category at routing time, and duplicate building or team
        ids would make lookups ambiguous.
        """
        team_ids = [team.id for team in self.teams]
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("Team ids must be unique within a campus.")

        building_ids = [building.id for building in self.buildings]
        if len(building_ids) != len(set(building_ids)):
            raise ValueError("Building ids must be unique within a campus.")

        if self.default_team_id is not None and self.default_team_id not in team_ids:
            raise ValueError(
                f"default_team_id {self.default_team_id!r} does not match any team."
            )
        return self
