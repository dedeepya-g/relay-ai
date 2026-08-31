"""ADK tool: decide whether a report describes a known incident.

Deduplication runs in two stages that fail in different ways, so they are kept
separate. :func:`find_candidate_incidents` is a cheap, deterministic Firestore
query that decides what is worth comparing; :func:`compare_incidents` is a
single model call that decides what actually matches. A bug in the first stage
silently shrinks the search space, which is why its ordering is explicit and
testable rather than folded into the prompt.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from config import get_settings
from models.common import DecisionActor, DecisionType, ReportStatus, utc_now
from models.decision import Decision
from models.duplicate import DuplicateDecision, DuplicateVerdict
from models.incident import Incident
from models.report import Report
from services.firestore_service import (
    get_report,
    list_deduplication_candidates,
    list_reports_for_incident,
    record_decision,
    update_report,
)
from services.gemini_service import GeminiError, generate_structured
from tools.merge_report_into_incident import merge_report_into_incident
from tools.open_incident import open_incident

logger = logging.getLogger(__name__)

#: How far back to look for an incident a new report might belong to. The
#: documented real-world failure is the same fault reported twice, fifteen days
#: apart, so a window measured in hours would miss the case deduplication
#: exists to catch.
CANDIDATE_WINDOW = timedelta(days=30)

#: Candidates sent to the model. Enough to cover a busy building, small enough
#: that every candidate still gets described in full rather than truncated.
MAX_CANDIDATES = 10

#: Evidence reports quoted per candidate, newest first.
MAX_EVIDENCE_PER_CANDIDATE = 5

SYSTEM_INSTRUCTION = """\
You decide whether a new facilities report describes the SAME underlying \
physical problem as an incident already being tracked, so that one problem is \
not dispatched to five crews and five problems are not hidden behind one \
ticket.

You are given one new report and a numbered list of candidate incidents, each \
with the reports already merged into it. Return one verdict.

same_incident -- the new report is another account of a problem already in the \
list. Set matched_incident_id to that incident's id, exactly as given.

different_incident -- the new report describes a separate problem. Sharing a \
building, a floor, or a category is not a match on its own.

needs_review -- the evidence genuinely supports more than one reading and a \
wrong guess would cost more than a human glance. Prefer this to a coin flip. \
Do not use it merely because the reporter was vague: vagueness on its own is \
not ambiguity, and a report that clearly belongs somewhere still belongs there \
however briefly it was written.

The case that most often belongs here is competition between candidates, not \
same-versus-new. When two or more candidates each account for the report and \
nothing in it separates them -- the same kind of fault, the same building, and \
the one detail that would tell them apart is exactly what the reporter did not \
give -- do not simply take the closest match. Merging into the wrong one of two \
open incidents hides a live fault behind a ticket raised for a different one, \
and unlike a split it does not correct itself: the second fault stops being \
visible to anyone. Name the candidates that compete and the single detail that \
would settle it.

What counts as the same problem:

One physical fault described in different words. "Leak in the third-floor \
restroom" and "bathroom floor upstairs is covered in water" are the same water \
on the same floor, seen by two people who describe rooms differently. \
Vocabulary differences -- restroom and bathroom, upstairs and third floor, \
burst and leaking -- are not evidence of different problems.

One fault with consequences in a connected space. Water travels. A leak on \
floor 3 produces a ceiling stain on floor 2, water spreading toward a \
stairwell, and water reaching an outlet down the corridor. These are the same \
incident reported from different vantage points, not new incidents, even when \
the reporter names a different floor or a different hazard. A report naming a \
hazard the original did not mention -- an electrical outlet, a blocked exit -- \
is usually the same fault getting worse, which is the most important case to \
catch, not evidence of a second fault.

Different stages of one fault. "Water is leaking", "water is spreading", and \
"the sink may have burst" can all describe one failure observed as it \
develops, or guessed at from its effects.

What does not count:

Two faults of the same category in the same building at the same time are \
different incidents unless something physically connects them. A clogged drain \
on floor 1 and a burst pipe on floor 3 are two problems. So are two separate \
broken card readers on different doors. Ask whether one repair visit fixes \
both: if a crew would have to do two unrelated jobs, they are different \
incidents.

An incident that has been resolved is not a match for a fresh report. A \
recurrence is a new problem with its own deadline.

reasoning -- explain the decision to a facilities manager reading the incident \
history months from now. Name the specific evidence that connects or separates \
the reports: the shared location, the direction water is travelling, the \
matching fixture. Do not restate the rules, do not mention confidence scores, \
and do not refer to candidates by their list number -- describe them by what \
they are. Two or three sentences.\
"""


def _floor_distance(left: str | None, right: str | None) -> int | None:
    """Return the number of floors between two labels, or ``None`` if unknown.

    Basement labels (``B1``, ``B2``) are treated as descending below floor 1 so
    that a basement is adjacent to the ground floor rather than incomparable.
    """
    def parse(label: str | None) -> int | None:
        if not label:
            return None
        text = label.strip().upper()
        if text.startswith("B") and text[1:].isdigit():
            # B1 sits directly below floor 1, B2 below that, so B{n} maps to
            # 1 - n and a basement is one floor from the ground floor.
            return 1 - int(text[1:])
        if text.lstrip("-").isdigit():
            return int(text)
        return None

    left_value, right_value = parse(left), parse(right)
    if left_value is None or right_value is None:
        return None
    return abs(left_value - right_value)


def _relevance_rank(report: Report, incident: Incident) -> int:
    """Rank one candidate; lower sorts first.

    Ordering is by how likely the candidate is to be the same problem, not by
    how similar the text looks. Same floor and same category is the ordinary
    duplicate. An adjacent floor in the same category ranks next, because that
    is where a leak's consequences show up, and excluding it would lose the
    case this project exists to catch.
    """
    same_category = incident.category == report.category
    distance = _floor_distance(report.location.floor, incident.location.floor)

    if same_category and distance == 0:
        return 0
    if same_category and distance == 1:
        return 1
    if same_category and distance is None:
        return 2
    if same_category:
        return 3
    if distance == 0:
        return 4
    return 5


def find_candidate_incidents(report: Report) -> list[Incident]:
    """Shortlist incidents the report might be a duplicate of.

    A pure Firestore read with no model call: it decides what is worth
    comparing, not what matches. Scoped to the report's building, because a
    problem observed in one building is not the same problem as one observed in
    another, then ordered by how plausibly the candidate is the same fault.

    Args:
        report: A triaged report. ``report.category`` drives the ranking and
            should be set; ranking still works without it, but same-category
            candidates lose their advantage.

    Returns:
        Up to :data:`MAX_CANDIDATES` live incidents, most relevant first.
    """
    if report.category is None:
        logger.warning(
            "Report %s has no category; deduplication candidates will be "
            "ranked on location alone.",
            report.id,
        )

    candidates = list_deduplication_candidates(
        campus_id=report.campus_id,
        building_id=report.location.building_id,
        since=utc_now() - CANDIDATE_WINDOW,
        limit=MAX_CANDIDATES * 3,
    )
    # Exclude the incident this report already belongs to: re-matching a report
    # against its own incident would be a no-op at best and a self-referential
    # audit entry at worst.
    candidates = [
        incident for incident in candidates if incident.id != report.incident_id
    ]
    candidates.sort(
        key=lambda incident: (
            _relevance_rank(report, incident),
            -incident.created_at.timestamp(),
        )
    )
    return candidates[:MAX_CANDIDATES]


def _describe_candidate(index: int, incident: Incident) -> str:
    """Render one candidate incident and the reports already merged into it."""
    location = incident.location
    header = (
        f"Candidate {index}\n"
        f"  incident_id: {incident.id}\n"
        f"  category:    {incident.category.value}\n"
        f"  status:      {incident.status.value}\n"
        f"  location:    floor {location.floor or '(unknown)'}, "
        f"room {location.room or '(unknown)'}\n"
        f"  opened:      {incident.created_at.isoformat()}\n"
        f"  title:       {incident.title}\n"
        f"  summary:     {incident.summary}"
    )

    evidence = list_reports_for_incident(incident.id)[-MAX_EVIDENCE_PER_CANDIDATE:]
    if not evidence:
        return f"{header}\n  reports merged so far: (none recorded)"

    lines = [f"{header}\n  reports merged so far ({len(evidence)} shown):"]
    for report in evidence:
        where = f"floor {report.location.floor or '?'}, room {report.location.room or '?'}"
        lines.append(f'    - [{where}] "{report.description}"')
    return "\n".join(lines)


def _build_prompt(report: Report, candidates: list[Incident]) -> str:
    """Assemble the comparison turn for one report against its shortlist."""
    location = report.location
    signals = report.triage.severity_signals if report.triage else []

    new_report = (
        "NEW REPORT\n"
        f"  category:  {report.category.value if report.category else '(untriaged)'}\n"
        f"  location:  building {location.building_id}, "
        f"floor {location.floor or '(not given)'}, "
        f"room {location.room or '(not given)'}\n"
        f"  submitted: {report.submitted_at.isoformat()}\n"
        f"  signals:   {', '.join(signals) if signals else '(none)'}\n"
        f'  text:      "{report.description}"'
    )
    described = "\n\n".join(
        _describe_candidate(index, incident)
        for index, incident in enumerate(candidates, start=1)
    )
    return f"{new_report}\n\nCANDIDATE INCIDENTS\n\n{described}"


def compare_incidents(
    report: Report, candidates: list[Incident]
) -> DuplicateDecision:
    """Decide whether the report describes one of the candidate incidents.

    Args:
        report: The triaged report to place.
        candidates: Shortlist from :func:`find_candidate_incidents`, most
            relevant first.

    Returns:
        The decision. With no candidates the result is ``different_incident``
        without a model call, since there is nothing to be a duplicate of.

    Raises:
        GeminiError: If the model cannot produce a valid decision after
            retries.
    """
    if not candidates:
        return DuplicateDecision(
            decision=DuplicateVerdict.DIFFERENT_INCIDENT,
            reasoning="No open incident in this building could be the same "
            "problem, so this report opens a new one.",
        )

    decision = generate_structured(
        _build_prompt(report, candidates),
        DuplicateDecision,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    # The model returns an id as free text, so it can name an incident that was
    # never offered. Treating that as a match would merge a report into an
    # arbitrary incident; downgrading to needs_review puts it in front of a
    # person instead.
    if decision.decision is DuplicateVerdict.SAME_INCIDENT:
        offered = {incident.id for incident in candidates}
        if decision.matched_incident_id not in offered:
            logger.warning(
                "Model matched report %s to unoffered incident %r; "
                "downgrading to needs_review.",
                report.id,
                decision.matched_incident_id,
            )
            return DuplicateDecision(
                decision=DuplicateVerdict.NEEDS_REVIEW,
                reasoning=(
                    "Automatic matching named an incident that was not among "
                    "the candidates considered, so this report needs a human "
                    "to place it."
                ),
            )

    logger.info(
        "Report %s compared against %d candidates: %s",
        report.id,
        len(candidates),
        decision.decision.value,
    )
    return decision


def _record(
    report: Report,
    decision: DuplicateDecision,
    outcome: str,
    candidates: list[Incident],
) -> None:
    """Append this deduplication judgment to the audit trail.

    Written for every outcome, not only ambiguous ones. "Why is this a separate
    incident?" needs an answer as much as "why were these merged?", and the
    candidates considered are part of that answer: they show what the decision
    was made against, including the incidents it ruled out.
    """
    record_decision(
        Decision(
            campus_id=report.campus_id,
            decision_type=DecisionType.DEDUPLICATION,
            decided_by=DecisionActor.MODEL,
            subject_type="reports",
            subject_id=report.id,
            outcome=outcome,
            rationale=decision.reasoning,
            tool_name="find_duplicate_incident",
            model=get_settings().gemini_model,
            inputs={
                "description": report.description,
                "category": report.category.value if report.category else None,
                "building_id": report.location.building_id,
                "floor": report.location.floor,
                "candidate_incident_ids": [incident.id for incident in candidates],
            },
            requires_review=decision.decision is DuplicateVerdict.NEEDS_REVIEW,
        )
    )


def find_duplicate_incident(report_id: str) -> dict[str, Any]:
    """Check whether a triaged report describes an already-tracked incident.

    Call this after ``triage_report``. Shortlists recent open incidents in the
    same building, compares them against the report, and then acts on the
    answer: a match merges the report into that incident, no match opens a new
    one, and a genuinely ambiguous case pauses the report for a person instead
    of guessing.

    Args:
        report_id: Id of the triaged report to match.

    Returns:
        A dict whose ``outcome`` is one of ``merged``, ``new_incident``, or
        ``needs_review``, alongside ``report_id``, ``incident_id`` (``None``
        for ``needs_review``), ``reasoning``, and ``candidates_considered``;
        or ``{"error": ...}`` if the report is missing or untriaged.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id!r}."}
    if report.category is None:
        return {
            "error": f"Report {report_id!r} has not been triaged yet; call "
            "triage_report first."
        }

    candidates = find_candidate_incidents(report)
    try:
        decision = compare_incidents(report, candidates)
    except GeminiError as exc:
        logger.exception("Deduplication failed for report %s", report_id)
        return {"error": f"Could not compare report {report_id!r}: {exc}"}

    result: dict[str, Any] = {
        "report_id": report_id,
        "reasoning": decision.reasoning,
        "candidates_considered": len(candidates),
    }

    if decision.decision is DuplicateVerdict.SAME_INCIDENT:
        merged = merge_report_into_incident(report_id, decision.matched_incident_id)
        if "error" in merged:
            return merged
        _record(
            report, decision, f"merged into {decision.matched_incident_id}", candidates
        )
        return {
            **result,
            "outcome": "merged",
            "incident_id": decision.matched_incident_id,
            "report_count": merged["report_count"],
        }

    if decision.decision is DuplicateVerdict.DIFFERENT_INCIDENT:
        opened = open_incident(report_id)
        if "error" in opened:
            return opened
        _record(report, decision, f"opened {opened['incident_id']}", candidates)
        return {
            **result,
            "outcome": "new_incident",
            "incident_id": opened["incident_id"],
            "title": opened["title"],
        }

    # needs_review: the report is parked, deliberately unlinked. Leaving
    # incident_id null is the whole point -- a caller that reads "no incident"
    # as "not a duplicate" would silently turn a declined judgment into a
    # split, which is the failure this verdict exists to prevent.
    update_report(report_id, {"status": ReportStatus.PENDING_REVIEW.value})
    _record(report, decision, "paused for human review", candidates)
    return {
        **result,
        "outcome": "needs_review",
        "incident_id": None,
        "status": ReportStatus.PENDING_REVIEW.value,
    }
