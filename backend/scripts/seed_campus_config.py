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
from models.campus_config import CampusConfig

logger = logging.getLogger(__name__)


def build_relay_university_config(campus_id: str) -> CampusConfig:
    """Build the demo configuration for Relay University.

    Defines the fictional campus the demo runs on: its buildings and their
    common aliases, the maintenance teams and which issue categories each owns,
    the SLA hours per priority, and the escalation policy.

    Args:
        campus_id: Id to store the configuration under.

    Returns:
        The configuration to write to Firestore.
    """
    raise NotImplementedError


def seed(campus_id: str, force: bool) -> None:
    """Write the campus configuration, refusing to clobber unless forced.

    Args:
        campus_id: Campus to seed.
        force: Overwrite an existing configuration document.

    Raises:
        SystemExit: If a configuration already exists and ``force`` is False.
    """
    raise NotImplementedError


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
