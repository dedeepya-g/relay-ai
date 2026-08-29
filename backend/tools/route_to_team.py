"""ADK tool: choose the maintenance team that owns an incident.

Routing is a lookup against the campus configuration, not a judgment. Which
team owns plumbing is a decision the campus already made and wrote down;
re-deciding it per incident would let Relay quietly contradict its own policy.
"""

from __future__ import annotations

import logging
from typing import Any

from models.campus_config import CampusConfig, MaintenanceTeam
from models.common import DecisionType, IssueCategory
from models.decision import Decision
from services.firestore_service import (
    get_campus_config,
    get_incident,
    record_decision,
    update_incident,
)

logger = logging.getLogger(__name__)


def _team_for_category(
    config: CampusConfig, category: IssueCategory
) -> tuple[MaintenanceTeam | None, bool]:
    """Find the team owning a category, falling back to the default team.

    Args:
        config: Campus configuration.
        category: Category to route.

    Returns:
        The team and whether the default was used. ``(None, True)`` when no
        team owns the category and no default is configured, which is a gap in
        the campus configuration rather than a routing failure.
    """
    for team in config.teams:
        if category in team.categories:
            return team, False

    if config.default_team_id is None:
        return None, True
    for team in config.teams:
        if team.id == config.default_team_id:
            return team, True
    return None, True


def route_to_team(incident_id: str) -> dict[str, Any]:
    """Route an incident to the maintenance team that should fix it.

    Call this after the incident has a category. Matches the category against
    team ownership in the campus config, falling back to the configured default
    team when no team owns it. The team's coverage window is reported alongside
    the assignment so a dispatcher can see whether the work lands inside
    staffed hours; it does not change which team is chosen.

    Args:
        incident_id: Id of the incident to route.

    Returns:
        A dict with ``incident_id``, ``team_id``, ``team_name``,
        ``coverage_hours``, ``used_fallback``, and ``rationale``; or
        ``{"error": ...}`` if the incident, campus configuration, or an owning
        team is missing.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id!r}."}
    config = get_campus_config(incident.campus_id)
    if config is None:
        return {"error": f"No campus configuration for {incident.campus_id!r}."}

    team, used_fallback = _team_for_category(config, incident.category)
    if team is None:
        return {
            "error": f"No team owns category {incident.category.value!r} and "
            f"campus {incident.campus_id!r} has no usable default team."
        }

    if used_fallback:
        logger.warning(
            "Category %s has no owning team; incident %s routed to the default "
            "team %s.",
            incident.category.value,
            incident_id,
            team.id,
        )
        rationale = (
            f"No team owns {incident.category.value} on this campus, so the "
            f"incident falls back to {team.name}."
        )
    else:
        rationale = f"{team.name} owns {incident.category.value} on this campus."

    update_incident(incident_id, {"assigned_team_id": team.id})
    record_decision(
        Decision(
            campus_id=incident.campus_id,
            decision_type=DecisionType.ROUTING,
            subject_type="incidents",
            subject_id=incident_id,
            outcome=f"routed to {team.id}",
            rationale=rationale,
            tool_name="route_to_team",
            model=None,
            inputs={
                "category": incident.category.value,
                "used_fallback": used_fallback,
            },
        )
    )

    return {
        "incident_id": incident_id,
        "team_id": team.id,
        "team_name": team.name,
        "coverage_hours": team.coverage_hours,
        "used_fallback": used_fallback,
        "rationale": rationale,
    }
