"""Seed the Relay University campus configuration into Firestore.

One-time setup: writes the buildings, maintenance teams, SLA windows, and
escalation policy the agent tools read at decision time.

Usage:
    cd backend
    python -m scripts.seed_campus_config [--campus-id relay-university] [--force]
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import configure_logging, get_settings
from models.campus_config import (
    Building,
    CampusConfig,
    EscalationPolicy,
    MaintenanceTeam,
    Room,
)
from models.common import IssueCategory, Priority, RoomType
from services.firestore_service import get_campus_config, upsert_campus_config

logger = logging.getLogger(__name__)

CAMPUS_NAME = "Relay University"
CAMPUS_TIMEZONE = "America/Los_Angeles"

#: Minutes allowed to resolve an incident, by priority. Compressed to minutes
#: so a live demo can watch a deadline pass and the escalation fire; a real
#: campus would run these in hours or days.
SLA_MINUTES: dict[Priority, int] = {
    Priority.CRITICAL: 2,
    Priority.HIGH: 5,
    Priority.MEDIUM: 15,
    Priority.LOW: 60,
}

#: Phrases that force a report to critical regardless of model judgment. These
#: describe conditions where a wrong call risks injury, so the gate is a plain
#: keyword match rather than a judgment the model is allowed to make.
EMERGENCY_KEYWORDS: list[str] = [
    "exposed wire",
    "smell of gas",
    "flooding",
    "blocked exit",
    "elevator entrapment",
    "power outage",
    "fire",
    "sparking",
]

DEFAULT_TEAM_ID = "team_general_maintenance"


def _harlow_science_center() -> Building:
    """Build the academic classroom-and-lab building.

    Four floors with a vertically aligned restroom stack (118 / 218 / 318) so
    that a leak on an upper floor and the ceiling damage it causes below are
    distinct rooms in the same column -- the shape of report the deduplication
    engine has to recognize as one incident.
    """
    return Building(
        id="bldg_harlow_science",
        name="Harlow Science Center",
        aliases=["Harlow", "Science Center", "HSC", "Harlow Hall"],
        floors=["B1", "1", "2", "3"],
        rooms=[
            Room(number="B12", floor="B1", room_type=RoomType.LAB,
                 name="Instrumentation Lab"),
            Room(number="B14", floor="B1", room_type=RoomType.LAB,
                 name="Materials Prep Lab"),
            Room(number="B18", floor="B1", room_type=RoomType.RESTROOM,
                 name="Lower Level Restroom"),
            Room(number="B20", floor="B1", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Lower Level Elevator Lobby"),
            Room(number="101", floor="1", room_type=RoomType.CLASSROOM,
                 name="Harlow Lecture Hall"),
            Room(number="105", floor="1", room_type=RoomType.CLASSROOM),
            Room(number="112", floor="1", room_type=RoomType.LAB,
                 name="General Chemistry Lab"),
            Room(number="118", floor="1", room_type=RoomType.RESTROOM,
                 name="First Floor Restroom (North)"),
            Room(number="120", floor="1", room_type=RoomType.ELEVATOR_LOBBY,
                 name="First Floor Elevator Lobby"),
            Room(number="130", floor="1", room_type=RoomType.COMMON_AREA,
                 name="Harlow Atrium"),
            Room(number="201", floor="2", room_type=RoomType.CLASSROOM),
            Room(number="205", floor="2", room_type=RoomType.CLASSROOM),
            Room(number="210", floor="2", room_type=RoomType.OFFICE,
                 name="Physics Faculty Suite"),
            Room(number="214", floor="2", room_type=RoomType.LAB,
                 name="Optics Lab"),
            Room(number="218", floor="2", room_type=RoomType.RESTROOM,
                 name="Second Floor Restroom (North)"),
            Room(number="220", floor="2", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Second Floor Elevator Lobby"),
            Room(number="301", floor="3", room_type=RoomType.CLASSROOM),
            Room(number="308", floor="3", room_type=RoomType.OFFICE,
                 name="Biology Department Office"),
            Room(number="312", floor="3", room_type=RoomType.LAB,
                 name="Biology Teaching Lab"),
            Room(number="318", floor="3", room_type=RoomType.RESTROOM,
                 name="Third Floor Restroom (North)"),
            Room(number="320", floor="3", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Third Floor Elevator Lobby"),
            Room(number="330", floor="3", room_type=RoomType.COMMON_AREA,
                 name="Third Floor Study Lounge"),
        ],
    )


def _ridgeway_library() -> Building:
    """Build the library and student commons.

    Mostly shared space: the rooms people report faults in here are common
    areas and restrooms, which draw many reports of one problem from many
    people -- the other half of the duplicate problem.
    """
    return Building(
        id="bldg_ridgeway_library",
        name="Ridgeway Library and Commons",
        aliases=["Ridgeway", "The Library", "Ridgeway Commons", "Main Library"],
        floors=["1", "2", "3"],
        rooms=[
            Room(number="100", floor="1", room_type=RoomType.COMMON_AREA,
                 name="Main Reading Room"),
            Room(number="104", floor="1", room_type=RoomType.COMMON_AREA,
                 name="Learning Commons"),
            Room(number="110", floor="1", room_type=RoomType.OFFICE,
                 name="Circulation Office"),
            Room(number="116", floor="1", room_type=RoomType.RESTROOM,
                 name="First Floor Restroom (East)"),
            Room(number="122", floor="1", room_type=RoomType.ELEVATOR_LOBBY,
                 name="First Floor Elevator Lobby"),
            Room(number="205", floor="2", room_type=RoomType.COMMON_AREA,
                 name="Quiet Study Floor"),
            Room(number="212", floor="2", room_type=RoomType.CLASSROOM,
                 name="Library Instruction Room"),
            Room(number="216", floor="2", room_type=RoomType.RESTROOM,
                 name="Second Floor Restroom (East)"),
            Room(number="222", floor="2", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Second Floor Elevator Lobby"),
            Room(number="305", floor="3", room_type=RoomType.COMMON_AREA,
                 name="Graduate Reading Room"),
            Room(number="316", floor="3", room_type=RoomType.RESTROOM,
                 name="Third Floor Restroom (East)"),
            Room(number="322", floor="3", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Third Floor Elevator Lobby"),
            Room(number="330", floor="3", room_type=RoomType.OFFICE,
                 name="Archives and Special Collections"),
        ],
    )


def _calloway_administration() -> Building:
    """Build the small administrative office building.

    Card-reader and lock faults concentrate here, which is what gives the
    access category somewhere real to route to.
    """
    return Building(
        id="bldg_calloway_admin",
        name="Calloway Administration Building",
        aliases=["Calloway", "Admin", "Admin Building", "Callaway"],
        floors=["1", "2"],
        rooms=[
            Room(number="101", floor="1", room_type=RoomType.OFFICE,
                 name="Office of the Registrar"),
            Room(number="106", floor="1", room_type=RoomType.OFFICE,
                 name="Student Accounts"),
            Room(number="112", floor="1", room_type=RoomType.COMMON_AREA,
                 name="Calloway Lobby"),
            Room(number="118", floor="1", room_type=RoomType.RESTROOM,
                 name="First Floor Restroom"),
            Room(number="120", floor="1", room_type=RoomType.ELEVATOR_LOBBY,
                 name="First Floor Elevator Lobby"),
            Room(number="201", floor="2", room_type=RoomType.OFFICE,
                 name="Provost Suite"),
            Room(number="208", floor="2", room_type=RoomType.OFFICE,
                 name="Human Resources"),
            Room(number="214", floor="2", room_type=RoomType.OFFICE,
                 name="Facilities Management Office"),
            Room(number="218", floor="2", room_type=RoomType.RESTROOM,
                 name="Second Floor Restroom"),
            Room(number="220", floor="2", room_type=RoomType.ELEVATOR_LOBBY,
                 name="Second Floor Elevator Lobby"),
        ],
    )


def _maintenance_teams() -> list[MaintenanceTeam]:
    """Build the maintenance teams and the categories each one owns.

    Coverage differs by trade on purpose: the failures that cannot wait for
    business hours are staffed around the clock, and the ones that can are not.
    Access Control owns elevator and safety work alongside locks and card
    readers because entrapments and safety calls need the after-hours dispatch
    path that team already has, not because the trades are alike. General
    Maintenance absorbs the cosmetic, custodial, and AV work and remains the
    fallback should a future category arrive without an owner.
    """
    return [
        MaintenanceTeam(
            id="team_plumbing",
            name="Plumbing Team",
            categories=[IssueCategory.PLUMBING],
            contact_email="plumbing@relay.edu",
            contact_phone="+1-555-0142",
            coverage_hours="24/7",
            escalation_contact="facilities.director@relay.edu",
        ),
        MaintenanceTeam(
            id="team_electrical",
            name="Electrical Team",
            categories=[IssueCategory.ELECTRICAL],
            contact_email="electrical@relay.edu",
            contact_phone="+1-555-0163",
            coverage_hours="24/7",
            escalation_contact="facilities.director@relay.edu",
        ),
        MaintenanceTeam(
            id="team_access_control",
            name="Access Control Team",
            categories=[
                IssueCategory.ACCESS,
                IssueCategory.ELEVATOR,
                IssueCategory.SAFETY,
            ],
            contact_email="accesscontrol@relay.edu",
            contact_phone="+1-555-0177",
            coverage_hours=(
                "Mon-Fri 07:00-19:00; after-hours lockouts, entrapments, and "
                "safety calls via Campus Safety dispatch"
            ),
            escalation_contact="security.manager@relay.edu",
        ),
        MaintenanceTeam(
            id="team_hvac",
            name="HVAC Team",
            categories=[IssueCategory.HVAC],
            contact_email="hvac@relay.edu",
            contact_phone="+1-555-0198",
            coverage_hours="Mon-Sun 06:00-22:00; building automation on-call 24/7",
            escalation_contact="facilities.director@relay.edu",
        ),
        MaintenanceTeam(
            id=DEFAULT_TEAM_ID,
            name="General Maintenance",
            categories=[
                IssueCategory.CUSTODIAL,
                IssueCategory.STRUCTURAL,
                IssueCategory.GROUNDS,
                IssueCategory.PEST,
                IssueCategory.IT_AV,
                IssueCategory.OTHER,
            ],
            contact_email="maintenance@relay.edu",
            contact_phone="+1-555-0110",
            coverage_hours="Mon-Fri 07:00-17:00",
            escalation_contact="operations.manager@relay.edu",
        ),
    ]


def build_relay_university_config(campus_id: str) -> CampusConfig:
    """Build the demo configuration for Relay University.

    Defines the fictional campus the demo runs on: its buildings and their
    common aliases, the maintenance teams and which issue categories each owns,
    the SLA windows per priority, and the escalation policy.

    Args:
        campus_id: Id to store the configuration under.

    Returns:
        The configuration to write to Firestore.
    """
    return CampusConfig(
        id=campus_id,
        name=CAMPUS_NAME,
        timezone=CAMPUS_TIMEZONE,
        buildings=[
            _harlow_science_center(),
            _ridgeway_library(),
            _calloway_administration(),
        ],
        teams=_maintenance_teams(),
        sla_minutes=SLA_MINUTES,
        emergency_keywords=EMERGENCY_KEYWORDS,
        escalation_policy=EscalationPolicy(
            grace_period_minutes=1,
            repeat_interval_minutes=2,
            max_level=3,
            notify_on_escalation=[
                "facilities.director@relay.edu",
                "operations.manager@relay.edu",
            ],
        ),
        default_team_id=DEFAULT_TEAM_ID,
    )


def _print_summary(config: CampusConfig) -> None:
    """Print what was written, so a seeding run can be checked at a glance."""
    room_count = sum(len(building.rooms) for building in config.buildings)
    owned = [category for team in config.teams for category in team.categories]

    print(f"campus:             {config.name} ({config.id})")
    print(f"buildings:          {len(config.buildings)}")
    for building in config.buildings:
        print(
            f"  {building.name:<38} "
            f"{len(building.floors)} floors, {len(building.rooms):>2} rooms"
        )
    print(f"rooms:              {room_count}")
    print(f"teams:              {len(config.teams)}")
    for team in config.teams:
        categories = ", ".join(category.value for category in team.categories)
        print(f"  {team.name:<38} {categories}")
    print(f"routed categories:  {len(owned)} ({', '.join(c.value for c in owned)})")
    print(f"default team:       {config.default_team_id}")
    sla = ", ".join(
        f"{priority.value}={minutes}m"
        for priority, minutes in config.sla_minutes.items()
    )
    print(f"sla_minutes:        {sla}")
    print(f"emergency keywords: {len(config.emergency_keywords)}")


def seed(campus_id: str, force: bool) -> None:
    """Write the campus configuration, refusing to clobber unless forced.

    Args:
        campus_id: Campus to seed.
        force: Overwrite an existing configuration document.

    Raises:
        SystemExit: If a configuration already exists and ``force`` is False.
    """
    config = build_relay_university_config(campus_id)

    # Short-circuit so --force never reads the existing document: an overwrite
    # has to work even when what is already stored predates the current schema
    # and would fail validation on the way in.
    if not force and get_campus_config(campus_id) is not None:
        raise SystemExit(
            f"Campus configuration {campus_id!r} already exists. "
            "Re-run with --force to overwrite it."
        )

    _print_summary(upsert_campus_config(config))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campus-id",
        default=None,
        help="Campus id to seed; defaults to RELAY_CAMPUS_ID from the environment.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing campus configuration.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Script entrypoint.

    Returns:
        A process exit code: 0 on success, 1 on a configuration error.
    """
    args = parse_args(argv)
    configure_logging()
    campus_id = args.campus_id or get_settings().campus_id
    seed(campus_id=campus_id, force=args.force)
    logger.info("Seeded campus configuration for %s", campus_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
