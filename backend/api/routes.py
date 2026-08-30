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
    OverdueSweepResponse,
    PendingReview,
    PendingReviewList,
    ReportIntakeResponse,
    ResolveReviewRequest,
    ResolveReviewResponse,
    RoomOption,
    StatusUpdateRequest,
    StatusUpdateResponse,
    TeamOption,
    WorkOrderSummary,
)
from agents.coordinator import coordinate
from config import get_settings
from models.common import DecisionType, IncidentStatus, Location, ReportStatus
from models.incident import Incident
from models.report import Report
from services.firestore_service import (
    create_report,
    get_campus_config,
    get_incident,
    get_report,
    get_work_order,
    list_decisions_for_subject,
    list_open_incidents,
    list_reports_by_status,
    list_reports_for_incident,
    update_report,
)
from services.storage_service import (
    PhotoRejectedError,
    generate_signed_url,
    upload_report_photo,
)
from tools.assign_priority import assign_priority
from tools.create_work_order import create_work_order
from tools.escalate_overdue_incidents import escalate_overdue_incidents
from tools.find_duplicate_incident import find_duplicate_incident
from tools.resolve_review import resolve_review
from tools.route_to_team import route_to_team
from tools.triage_report import triage_report
from tools.update_incident_status import ALLOWED_TRANSITIONS, update_incident_status

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


def _photo_url(report: Report) -> str | None:
    """Return a signed URL for a report's photo, or ``None`` if unavailable.

    Signing can fail for reasons unrelated to whether the photo exists --
    local credentials without a private key, a transient IAM error -- and none
    of those should take down the whole incident view over one report's photo.
    """
    if report.photo_uri is None:
        return None
    try:
        return generate_signed_url(report.photo_uri)
    except Exception:  # noqa: BLE001 - signing failure degrades to no photo
        logger.warning(
            "Could not sign URL for photo %s on report %s",
            report.photo_uri,
            report.id,
            exc_info=True,
        )
        return None


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
        work_order_ids=incident.work_order_ids,
        escalation_level=incident.escalation_level,
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
    request. A photo is stored before triage runs, so its ``gs://`` URI is on
    the report by the time triage reads it for multimodal analysis.
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

    photo_stored = False
    if photo is not None:
        data = await photo.read()
        try:
            gcs_uri = upload_report_photo(
                report.id,
                data,
                content_type=photo.content_type or "application/octet-stream",
                filename=photo.filename,
            )
        except PhotoRejectedError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from None
        report = update_report(report.id, {"photo_uri": gcs_uri})
        photo_stored = True

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
        photo_stored=photo_stored,
    )

    incident_id = dedup.get("incident_id")
    if incident_id is None:
        # Deduplication declined to place this report. The coordinator decides
        # what to do about that -- ask the reporter something, place it, or
        # agree a person is needed -- rather than the report simply waiting.
        followup = await coordinate(
            report_id=report.id,
            outcome=dedup["outcome"],
            dedup_reasoning=dedup["reasoning"],
        )
        response.coordinator_actions = followup["actions"]
        response.coordinator_reasoning = followup["reasoning"] or None
        placed = get_report(report.id)
        if placed is not None:
            response.report_status = placed.status
            response.incident_id = placed.incident_id
            if placed.incident_id:
                response.outcome = "merged"
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

    # Dispatch last, once the incident has both a priority and a team. This is
    # idempotent, so a report merging into an incident that is already being
    # worked returns the existing ticket instead of sending a second crew.
    dispatch = create_work_order(incident_id)

    response.priority = priority["priority"]
    response.sla_due_at = priority["sla_due_at"]
    response.evidence_count = priority["evidence_count"]
    response.team_assigned = routing["team_id"]
    response.team_name = routing["team_name"]
    response.work_order_ticket = dispatch.get("ticket")
    response.reasoning["prioritization"] = priority["rationale"]
    response.reasoning["routing"] = routing["rationale"]

    # Everything above is deterministic and already recorded. The coordinator
    # runs last, reads the resulting state, and decides what follow-up it
    # warrants. It cannot change any of the decisions it is reacting to.
    followup = await coordinate(
        report_id=report.id,
        outcome=dedup["outcome"],
        incident_id=incident_id,
        previous_priority=priority["previous_priority"],
        new_priority=priority["priority"],
        dedup_reasoning=dedup["reasoning"],
        evidence_count=priority["evidence_count"],
    )
    response.coordinator_actions = followup["actions"]
    response.coordinator_reasoning = followup["reasoning"] or None
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
                photo_url=_photo_url(report),
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
    "/incidents/{incident_id}/status",
    response_model=StatusUpdateResponse,
    tags=["incidents"],
)
async def update_status(
    incident_id: str, payload: StatusUpdateRequest
) -> StatusUpdateResponse:
    """Move an incident to a new lifecycle status.

    The tool owns the rules -- which transitions are legal, and that resolving
    requires notes -- and remains the only thing that writes the status. The
    checks here exist solely to choose a status code: an unknown status is a
    malformed request, an illegal transition conflicts with the incident's
    current state, and the two deserve different codes. Legality is read from
    the tool's own ``ALLOWED_TRANSITIONS`` rather than restated, so the table
    stays the single source of truth.
    """
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No incident {incident_id!r}.",
        )

    try:
        target = IncidentStatus(payload.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status {payload.new_status!r}; expected one of "
            f"{sorted(item.value for item in IncidentStatus)}.",
        ) from None

    allowed = ALLOWED_TRANSITIONS.get(incident.status, frozenset())
    if target is not incident.status and target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move incident {incident_id!r} from "
            f"{incident.status.value!r} to {target.value!r}. Allowed from "
            f"{incident.status.value!r}: "
            f"{sorted(item.value for item in allowed) or 'nothing'}.",
        )

    result = update_incident_status(
        incident_id, status=target.value, notes=payload.notes
    )
    if "error" in result:
        # Everything reachable here is a well-formed request the tool still
        # refuses -- resolving without notes being the live case.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
        )

    updated = get_incident(incident_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No incident {incident_id!r}.",
        )

    return StatusUpdateResponse(
        incident=_summarize(updated, _team_names()),
        previous_status=result["previous_status"],
        changed=result["changed"],
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


@router.get(
    "/work_orders/{work_order_id}",
    response_model=WorkOrderSummary,
    tags=["work orders"],
)
async def get_work_order_detail(work_order_id: str) -> WorkOrderSummary:
    """Return one dispatched work order.

    Fetched by id rather than embedded in the incident payload: an incident
    carries its work order ids, and a caller that does not display them should
    not pay to load them.
    """
    work_order = get_work_order(work_order_id)
    if work_order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No work order {work_order_id!r}.",
        )

    return WorkOrderSummary(
        work_order_id=work_order.id,
        ticket=work_order.ticket,
        incident_id=work_order.incident_id,
        team_id=work_order.team_id,
        team_name=_team_names().get(work_order.team_id),
        status=work_order.status,
        priority=work_order.priority,
        due_at=work_order.due_at,
        created_at=work_order.created_at,
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


@router.post(
    "/admin/check-overdue", response_model=OverdueSweepResponse, tags=["admin"]
)
async def check_overdue() -> OverdueSweepResponse:
    """Run the overdue sweep once and report what it escalated.

    Relay is meant to run this on a schedule. Exposing it as an endpoint keeps
    the demo honest: the sweep that runs here is the same function a scheduler
    would call, with no shortcut for being triggered by hand.
    """
    result = escalate_overdue_incidents(get_settings().campus_id)
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result["error"]
        )
    return OverdueSweepResponse(**result)
