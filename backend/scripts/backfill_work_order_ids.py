"""Repair incidents whose ``work_order_ids`` never recorded their work orders.

Dispatch used to write the work order and flip the incident to ``assigned``
without appending the new id to the incident, so the link existed in one
direction only: a work order named its incident, but the incident reported no
work orders. ``create_work_order`` now writes both sides, and this script
repairs the incidents raised before it did.

Safe to re-run. The new array is the existing one with anything missing
appended, so the write is additive: an id already stored keeps both its
presence and its position, and a second run finds nothing to change.

Usage:
    cd backend
    python -m scripts.backfill_work_order_ids            # dry run, writes nothing
    python -m scripts.backfill_work_order_ids --apply    # perform the writes
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from config import configure_logging, get_firestore_client

logger = logging.getLogger(__name__)

INCIDENTS_COLLECTION = "incidents"
WORK_ORDERS_COLLECTION = "work_orders"


def _work_orders_by_incident(db: Any) -> dict[str, list[tuple[Any, str, str | None]]]:
    """Group every work order by the incident it references, oldest first.

    Ordering is by ``created_at`` so a repaired array reads chronologically,
    matching the order dispatch would have produced. Work orders with no
    timestamp sort last rather than crashing the comparison.
    """
    grouped: dict[str, list[tuple[Any, str, str | None]]] = {}
    for snapshot in db.collection(WORK_ORDERS_COLLECTION).stream():
        data = snapshot.to_dict()
        incident_id = data.get("incident_id")
        if not incident_id:
            logger.warning(
                "Work order %s has no incident_id; skipping.", snapshot.id
            )
            continue
        grouped.setdefault(incident_id, []).append(
            (data.get("created_at"), snapshot.id, data.get("ticket"))
        )
    for entries in grouped.values():
        entries.sort(key=lambda entry: (entry[0] is None, entry[0]))
    return grouped


def backfill(apply: bool) -> int:
    """Align every incident's ``work_order_ids`` with the work orders it owns.

    Args:
        apply: Write the changes. When False, report what would change and
            leave Firestore untouched.

    Returns:
        The number of incidents that changed, or would change on a dry run.
    """
    db = get_firestore_client()
    grouped = _work_orders_by_incident(db)
    incidents = {
        snapshot.id: snapshot.to_dict()
        for snapshot in db.collection(INCIDENTS_COLLECTION).stream()
    }

    orphans = sorted(set(grouped) - set(incidents))
    if orphans:
        logger.warning("Work orders reference unknown incidents: %s", orphans)

    changed = 0
    for incident_id, data in sorted(incidents.items()):
        existing: list[str] = list(data.get("work_order_ids") or [])
        discovered = [wo_id for _, wo_id, _ in grouped.get(incident_id, [])]

        # Existing ids come first, so the stored array is a prefix of the
        # result. That is what makes this additive rather than a replacement,
        # and it is asserted rather than assumed before anything is written.
        merged = list(dict.fromkeys([*existing, *discovered]))
        if not set(existing) <= set(merged) or merged[: len(existing)] != existing:
            raise SystemExit(
                f"Refusing to write {incident_id!r}: the merge would drop or "
                f"reorder existing ids ({existing} -> {merged})."
            )

        if merged == existing:
            continue

        changed += 1
        tickets = [ticket for _, _, ticket in grouped.get(incident_id, [])]
        print(f"{incident_id}  status={data.get('status')}")
        print(f"   tickets : {tickets}")
        print(f"   before  : {existing}")
        print(f"   after   : {merged}")
        if apply:
            db.collection(INCIDENTS_COLLECTION).document(incident_id).update(
                {"work_order_ids": merged}
            )
            print("   written")
        print()

    verb = "Updated" if apply else "Would update"
    print(
        f"{verb} {changed} incident(s); "
        f"{len(incidents) - changed} already correct."
    )
    if not apply and changed:
        print("Dry run: nothing was written. Re-run with --apply.")
    return changed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes. Without it the script only reports them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Script entrypoint.

    Returns:
        A process exit code; 0 whether or not anything needed repairing.
    """
    args = parse_args(argv)
    configure_logging()
    backfill(apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
