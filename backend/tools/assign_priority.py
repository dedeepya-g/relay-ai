"""ADK tool: set an incident's priority and SLA deadline."""

from __future__ import annotations

from typing import Any


def assign_priority(incident_id: str) -> dict[str, Any]:
    """Assign a priority to an incident and derive its SLA deadline.

    Call this when an incident is opened and again whenever new evidence
    arrives. Weighs safety risk, how many people are affected, how many reports
    corroborate the problem, and how fast it is getting worse, then applies the
    campus SLA policy for the chosen priority.

    Args:
        incident_id: Id of the incident to prioritize.

    Returns:
        A dict with ``incident_id``, ``priority``, ``previous_priority``,
        ``sla_due_at``, ``rationale``, and ``confidence``.
    """
    raise NotImplementedError
