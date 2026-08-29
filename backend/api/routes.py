"""HTTP routes for the Relay API.

Wiring only. Each route validates its input, calls tools that are already
implemented and tested, and shapes the result for the wire. No route decides
anything the pipeline does not already decide, so what the API does is exactly
what the pipeline tests cover.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from api.schemas import (
    BuildingOption,
    CampusResponse,
    DecisionEntry,
    IncidentDetail,
    IncidentList,
    IncidentSummary,
    LinkedReport,
    PendingReview,
    PendingReviewList,
    ReportIntakeResponse,
    ResolveReviewRequest,
    ResolveReviewResponse,
    RoomOption,
    TeamOption,
)
from config import get_settings
from models.common import DecisionType, Location, ReportStatus
from models.incident import Incident
from models.report import Report
from services.firestore_service import (
    create_report,
    get_campus_config,
    get_incident,
    get_report,
    list_decisions_for_subject,
    list_open_incidents,
    list_reports_by_status,
    list_reports_for_incident,
)
from tools.assign_priority import assign_priority
from tools.find_duplicate_incident import find_duplicate_incident
from tools.resolve_review import resolve_review
from tools.route_to_team import route_to_team
from tools.triage_report import triage_report

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_INCIDENTS = 200


def _team_names() -> dict[str, str]:
    """Map team ids to display names from the campus configuration.

    Resolved server-side so a raw API response reads the same way the UI does;
    a client should never have to know that ``team_plumbing`` means "Plumbing
    Team". Returns an empty map if the campus is unseeded, in which case the
    id is shown unresolved rather than the request failing.
    """
    config = get_campus_config(get_settings().campus_id)
    return {team.id: team.name for team in config.teams} if config else {}


def _summarize(incident: Incident, team_names: dict[str, str]) -> IncidentSummary:
    """Project an incident onto its list representation."""
    return IncidentSummary(
        incident_id=incident.id,
        title=incident.title,
        category=incident.category,
        priority=incident.priority,
        status=incident.status,
        building_id=incident.location.building_id,
        floor=incident.location.floor,
        room=incident.location.room,
        assigned_team_id=incident.assigned_team_id,
        assigned_team_name=team_names.get(incident.assigned_team_id or ""),
        report_count=len(incident.report_ids),
        sla_due_at=incident.sla_due_at,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


@router.post(
    "/reports",
    response_model=ReportIntakeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
)
async def submit_report(
    description: str = Form(..., min_length=1, max_length=4000),
    building_id: str = Form(...),
    floor: str | None = Form(default=None),
    room: str | None = Form(default=None),
    detail: str | None = Form(default=None),
    reporter_email: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
) -> ReportIntakeResponse:
    """Submit a facility report and run it through the pipeline.

    The report is classified, checked against open incidents in the same
    building, and then either merged, opened as a new incident, or paused for
    human review. Priority and routing run only when the report was actually
    placed: a paused report deliberately has neither, because assigning them
    would imply a decision Relay declined to make.

    Fields arrive as form data so that a photo can be attached to the same
    request. A photo is accepted and acknowledged but not stored, since photo
    storage is not implemented yet.
    """
    report = create_report(
        Report(
            campus_id=get_settings().campus_id,
            description=description,
            location=Location(
                building_id=building_id, floor=floor, room=room, detail=detail
            ),
            reporter_email=reporter_email,
        )
    )

    triage = triage_report(report.id)
    if "error" in triage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=triage["error"]
        )

    dedup = find_duplicate_incident(report.id)
    if "error" in dedup:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=dedup["error"]
        )

    response = ReportIntakeResponse(
        report_id=report.id,
        outcome=dedup["outcome"],
        incident_id=dedup.get("incident_id"),
        report_status=ReportStatus.PENDING_REVIEW
        if dedup["outcome"] == "needs_review"
        else ReportStatus.LINKED,
        issue_type=triage["issue_type"],
        is_potential_emergency=triage["is_potential_emergency"],
        severity_signals=triage["severity_signals"],
        missing_fields=triage["missing_fields"],
        reasoning={
            "triage": triage["confidence_note"],
            "deduplication": dedup["reasoning"],
        },
        photo_received=photo is not None,
        photo_stored=False,
    )

    incident_id = dedup.get("incident_id")
    if incident_id is None:
        return response

    priority = assign_priority(incident_id)
    if "error" in priority:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=priority["error"]
        )
    routing = route_to_team(incident_id)
    if "error" in routing:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=routing["error"]
        )

    response.priority = priority["priority"]
    response.sla_due_at = priority["sla_due_at"]
    response.evidence_count = priority["evidence_count"]
    response.team_assigned = routing["team_id"]
    response.team_name = routing["team_name"]
    response.reasoning["prioritization"] = priority["rationale"]
    response.reasoning["routing"] = routing["rationale"]
    return response


@router.get("/incidents", response_model=IncidentList, tags=["incidents"])
async def list_incidents(
    limit: int = Query(default=50, ge=1, le=MAX_INCIDENTS)
) -> IncidentList:
    """List incidents that are still live work, newest first.

    Resolved and closed incidents are omitted: this is the dispatch view, not
    the archive.
    """
    incidents = list_open_incidents(get_settings().campus_id, limit=limit)
    team_names = _team_names()
    summaries = [_summarize(incident, team_names) for incident in incidents]
    return IncidentList(incidents=summaries, count=len(summaries))


@router.get(
    "/incidents/{incident_id}", response_model=IncidentDetail, tags=["incidents"]
)
async def get_incident_detail(incident_id: str) -> IncidentDetail:
    """Return one incident with its evidence and the reasoning behind it.

    The decision trail covers both the incident and every report merged into
    it, because the judgments that matter most -- why these reports were
    treated as one problem -- are recorded against the reports.
    """
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No incident {incident_id!r}.",
        )

    reports = list_reports_for_incident(incident_id)
    decisions = list_decisions_for_subject(incident_id)
    for report in reports:
        decisions.extend(list_decisions_for_subject(report.id))
    decisions.sort(key=lambda decision: decision.created_at)

    return IncidentDetail(
        incident=_summarize(incident, _team_names()),
        summary=incident.summary,
        reports=[
            LinkedReport(
                report_id=report.id,
                description=report.description,
                status=report.status,
                floor=report.location.floor,
                room=report.location.room,
                is_potential_emergency=bool(
                    report.triage and report.triage.is_potential_emergency
                ),
                severity_signals=report.triage.severity_signals
                if report.triage
                else [],
                submitted_at=report.submitted_at,
            )
            for report in reports
        ],
        decisions=[
            DecisionEntry(
                decision_id=decision.id,
                decision_type=decision.decision_type.value,
                decided_by=decision.decided_by.value,
                subject_id=decision.subject_id,
                outcome=decision.outcome,
                rationale=decision.rationale,
                model=decision.model,
                created_at=decision.created_at,
            )
            for decision in decisions
        ],
    )


@router.post(
    "/reports/{report_id}/resolve",
    response_model=ResolveReviewResponse,
    tags=["reports"],
)
async def resolve_report_review(
    report_id: str, payload: ResolveReviewRequest
) -> ResolveReviewResponse:
    """Apply a person's decision to a report Relay paused for review.

    The state checks happen here rather than by reading the tool's error text,
    so a missing report and an already-resolved one get distinct status codes.
    """
    report = get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report {report_id!r}.",
        )
    if report.status is not ReportStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report {report_id!r} is {report.status.value}, not "
            "awaiting review.",
        )

    result = resolve_review(
        report_id,
        resolution=payload.resolution,
        incident_id=payload.incident_id,
        note=payload.note,
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )

    return ResolveReviewResponse(
        report_id=result["report_id"],
        outcome=result["outcome"],
        incident_id=result["incident_id"],
        resolved_by=result["resolved_by"],
    )


@router.get("/campus", response_model=CampusResponse, tags=["campus"])
async def get_campus() -> CampusResponse:
    """Return the reference data a client needs to submit and label reports.

    Buildings, floors, and rooms come from the seeded campus configuration, so
    the locations a reporter can choose are exactly the locations routing and
    deduplication already understand. Duplicating them in the client would let
    the two drift apart silently.
    """
    config = get_campus_config(get_settings().campus_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This campus has not been configured yet. Seed it with "
            "scripts/seed_campus_config.py.",
        )

    return CampusResponse(
        campus_id=config.id,
        name=config.name,
        timezone=config.timezone,
        buildings=[
            BuildingOption(
                building_id=building.id,
                name=building.name,
                aliases=building.aliases,
                floors=building.floors,
                rooms=[
                    RoomOption(
                        number=room.number,
                        floor=room.floor,
                        room_type=room.room_type,
                        name=room.name,
                    )
                    for room in building.rooms
                ],
            )
            for building in config.buildings
        ],
        teams=[
            TeamOption(
                team_id=team.id,
                name=team.name,
                categories=team.categories,
                coverage_hours=team.coverage_hours,
            )
            for team in config.teams
        ],
        sla_minutes=config.sla_minutes,
    )


@router.get("/reviews", response_model=PendingReviewList, tags=["reports"])
async def list_pending_reviews() -> PendingReviewList:
    """List reports Relay declined to place, awaiting a human decision.

    These reports belong to no incident by design, so they cannot be found by
    walking the incident list. Each carries the reasoning from the
    deduplication decision that paused it, so a reviewer can see what Relay was
    unsure about without opening anything.
    """
    reports = list_reports_by_status(
        get_settings().campus_id, ReportStatus.PENDING_REVIEW
    )

    entries: list[PendingReview] = []
    for report in reports:
        paused = next(
            (
                decision.rationale
                for decision in list_decisions_for_subject(report.id)
                if decision.decision_type is DecisionType.DEDUPLICATION
            ),
            "",
        )
        entries.append(
            PendingReview(
                report_id=report.id,
                description=report.description,
                building_id=report.location.building_id,
                floor=report.location.floor,
                room=report.location.room,
                issue_type=report.category,
                is_potential_emergency=bool(
                    report.triage and report.triage.is_potential_emergency
                ),
                severity_signals=report.triage.severity_signals
                if report.triage
                else [],
                reasoning=paused,
                submitted_at=report.submitted_at,
            )
        )
    return PendingReviewList(reports=entries, count=len(entries))
