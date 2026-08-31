"""The Incident Coordinator: an ADK agent that reacts to pipeline outcomes.

By the time this agent runs, the deterministic pipeline has already finished.
A report has been classified, matched against open incidents, prioritised,
routed, and dispatched, and every one of those decisions is already recorded.
The coordinator changes none of them.

What it decides is what should happen *next*, which the pipeline has no rule
for: whether a jump in priority is worth telling the team about, whether an
incident that keeps accumulating evidence needs an escalation sweep, and --
the case it earns its keep on -- what to do with a report deduplication
declined to place. Left alone, such a report simply waits for a person. The
coordinator looks at the same evidence and often finds a better answer: ask the
reporter one specific question, place the report itself, or agree that a human
is genuinely needed.

Its tools wrap the pipeline's existing tools rather than reimplementing them,
so an action the coordinator takes is the same action the pipeline would have
taken, with the same validation behind it.
"""

from __future__ import annotations

import logging
import os
import traceback
from functools import lru_cache
from typing import Any

from config import get_settings
from models.common import DecisionActor, DecisionType, ReportStatus, utc_now
from models.decision import Decision
from services.firestore_service import (
    get_incident,
    get_report,
    list_reports_for_incident,
    record_decision,
    update_report,
)
from tools.escalate_overdue_incidents import escalate_overdue_incidents
from tools.merge_report_into_incident import merge_report_into_incident
from tools.open_incident import open_incident

logger = logging.getLogger(__name__)

APP_NAME = "relay-coordinator"

#: ADK reaches Gemini through the same google-genai client the rest of Relay
#: uses, and reads its backend from the environment. Setting these from Relay's
#: own settings keeps the agent on the identical project, model, and location
#: as every other model call, rather than a second configuration that could
#: drift.
def _configure_backend() -> None:
    settings = get_settings()
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.project_id)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gemini_location)


def _record_action(
    *,
    campus_id: str,
    subject_type: str,
    subject_id: str,
    outcome: str,
    rationale: str,
    tool_name: str,
    inputs: dict[str, Any],
) -> str:
    """Write one agent action to the audit trail and return its decision id.

    Every tool below that changes something calls this. Without it an action
    the agent took would exist only as a log line: the state would move and the
    trail would not say who moved it, which is the one thing the trail is for.
    ``tool_name`` is the specific tool rather than ``incident_coordinator``, so
    an action is distinguishable from the per-invocation summary
    :func:`coordinate` records alongside it.
    """
    decision = record_decision(
        Decision(
            campus_id=campus_id,
            decision_type=DecisionType.COORDINATION,
            decided_by=DecisionActor.AGENT,
            subject_type=subject_type,
            subject_id=subject_id,
            outcome=outcome,
            rationale=rationale,
            tool_name=tool_name,
            model=get_settings().gemini_model,
            inputs=inputs,
        )
    )
    return decision.id


# --- Tools ------------------------------------------------------------------
# Every tool is a thin wrapper. None of them re-runs triage, re-compares
# incidents, recomputes priority, or re-routes: those decisions are already
# made and recorded before this agent is invoked.


def get_incident_state(incident_id: str) -> dict[str, Any]:
    """Read an incident's current state and the reports supporting it.

    Use this to understand what an incident looks like now before deciding
    whether any follow-up is warranted.

    Args:
        incident_id: Id of the incident to inspect.

    Returns:
        The incident's title, category, priority, status, assigned team,
        escalation level, and the description of every report merged into it.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id}."}
    reports = list_reports_for_incident(incident_id)
    return {
        "incident_id": incident.id,
        "title": incident.title,
        "category": incident.category.value,
        "priority": incident.priority.value,
        "status": incident.status.value,
        "assigned_team_id": incident.assigned_team_id,
        "escalation_level": incident.escalation_level,
        "report_count": len(reports),
        "reports": [
            {
                "description": report.description,
                "floor": report.location.floor,
                "room": report.location.room,
                "is_potential_emergency": bool(
                    report.triage and report.triage.is_potential_emergency
                ),
                "severity_signals": report.triage.severity_signals
                if report.triage
                else [],
            }
            for report in reports
        ],
    }


def notify_team_priority_change(
    incident_id: str, previous_priority: str, new_priority: str, reason: str
) -> dict[str, Any]:
    """Tell the assigned team that an incident's priority has moved.

    Use this when a priority change is material enough that the team working
    the incident should know before they next look at their queue. A change
    into critical almost always qualifies; a change between the lower levels
    usually does not.

    Args:
        incident_id: Incident whose priority changed.
        previous_priority: The level it held before.
        new_priority: The level it holds now.
        reason: One sentence a dispatcher would understand, explaining why the
            team is being told.

    Returns:
        Confirmation, including the team notified.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id}."}

    # Relay has no messaging integration, so the trail entry *is* the
    # notification: it lands on the incident where the team already looks,
    # rather than in a channel nobody has connected yet. That makes recording
    # it the substance of this tool, not bookkeeping about it -- a log line
    # would leave the team never told and the record showing nothing.
    decision_id = _record_action(
        campus_id=incident.campus_id,
        subject_type="incidents",
        subject_id=incident_id,
        outcome=f"notified {incident.assigned_team_id or 'the assigned team'}",
        rationale=reason,
        tool_name="notify_team_priority_change",
        inputs={
            "previous_priority": previous_priority,
            "new_priority": new_priority,
            "notified_team_id": incident.assigned_team_id,
        },
    )
    logger.info(
        "Coordinator notified %s: %s -> %s on %s (%s)",
        incident.assigned_team_id,
        previous_priority,
        new_priority,
        incident_id,
        decision_id,
    )
    return {
        "notified_team_id": incident.assigned_team_id,
        "incident_id": incident_id,
        "previous_priority": previous_priority,
        "new_priority": new_priority,
        "reason": reason,
        "decision_id": decision_id,
    }


def run_escalation_sweep() -> dict[str, Any]:
    """Run the overdue sweep across the campus.

    Use this only when an incident looks like it may already be past its
    deadline. The sweep applies the campus escalation policy itself, including
    the grace period and the interval between raises, so calling it when
    nothing is overdue is harmless but pointless.

    Returns:
        How many incidents were past deadline and how many the policy raised.
    """
    result = escalate_overdue_incidents(get_settings().campus_id)
    return {
        "checked_count": result.get("checked_count", 0),
        "escalated_count": result.get("escalated_count", 0),
        "escalations": result.get("escalations", []),
    }


def request_missing_information(report_id: str, question: str) -> dict[str, Any]:
    """Record one specific question to put back to the reporter.

    Use this when a report cannot be placed only because of a detail the
    reporter could supply in a sentence -- most often which floor or room. Ask
    exactly one question, phrased as you would say it to them.

    Args:
        report_id: Report that is missing something.
        question: The question to ask, in plain words.

    Returns:
        Confirmation that the question was recorded.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id}."}

    # Persisted onto the report, not just recorded. A question that lives only
    # in the decision history is one nobody answers: the person who picks this
    # report up reads the report.
    update_report(
        report_id,
        {"pending_question": question, "question_asked_at": utc_now()},
    )
    decision_id = _record_action(
        campus_id=report.campus_id,
        subject_type="reports",
        subject_id=report_id,
        outcome="asked the reporter for a missing detail",
        rationale=question,
        tool_name="request_missing_information",
        inputs={"question": question, "report_status": report.status.value},
    )
    logger.info("Coordinator asked about %s: %s (%s)", report_id, question, decision_id)
    return {
        "report_id": report_id,
        "question": question,
        "awaiting_reporter": True,
        "decision_id": decision_id,
    }


def merge_report(report_id: str, incident_id: str) -> dict[str, Any]:
    """Attach a report to an incident it belongs to.

    Use this when the evidence supports one incident clearly enough that
    waiting for a person would only delay the work.

    Args:
        report_id: Report to attach.
        incident_id: Incident it belongs to.

    Returns:
        The incident and how many reports it now holds.
    """
    return merge_report_into_incident(report_id, incident_id)


def create_new_incident(report_id: str) -> dict[str, Any]:
    """Open a new incident for a report that belongs to none of the candidates.

    Use this when the report describes a distinct problem, so that work can
    start rather than waiting on a review queue.

    Args:
        report_id: Report to open an incident for.

    Returns:
        The new incident's id and title.
    """
    return open_incident(report_id)


def flag_for_human_review(report_id: str, reason: str) -> dict[str, Any]:
    """Leave a report waiting for a person, and say what they need to settle.

    Use this when the evidence genuinely supports more than one reading and
    choosing wrongly would cost more than the wait -- not merely because the
    report is short or vague.

    Args:
        report_id: Report to leave in review.
        reason: What a reviewer needs to decide, in one sentence.

    Returns:
        Confirmation that the report remains in review.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id}."}

    # Actually park it. Deduplication may already have set this status, but the
    # agent can also be asked about a report that reached it another way, and a
    # tool whose whole promise is "this now waits for a person" must not depend
    # on someone else having set that state.
    if report.status is not ReportStatus.PENDING_REVIEW:
        update_report(report_id, {"status": ReportStatus.PENDING_REVIEW.value})
    decision_id = _record_action(
        campus_id=report.campus_id,
        subject_type="reports",
        subject_id=report_id,
        outcome="left for human review",
        rationale=reason,
        tool_name="flag_for_human_review",
        inputs={
            "previous_status": report.status.value,
            "status": ReportStatus.PENDING_REVIEW.value,
        },
    )
    logger.info("Coordinator left %s for review: %s (%s)", report_id, reason, decision_id)
    return {
        "report_id": report_id,
        "awaiting_human": True,
        "reason": reason,
        "decision_id": decision_id,
    }


INSTRUCTION = """\
You are Relay's incident coordinator for a university facilities team.

A deterministic pipeline has already run before you. It classified the report, \
decided whether it described a problem already being tracked, set a priority \
from campus policy, chose the owning team, and raised a work order. Those \
decisions are made and recorded. You do not revisit them, and you have no \
tools to do so.

Your job is the question the pipeline has no rule for: given what just \
happened, what should happen next? Doing nothing is very often the right \
answer, and choosing it is a real decision, not a failure to act.

When a report was merged or opened an incident, consider whether anything \
warrants follow-up:
- If priority moved materially -- most importantly into critical -- tell the \
assigned team with notify_team_priority_change.
- If priority did not move, or moved between lower levels, say so and stop. Do \
not notify a team twice about the same level.
- If an incident is accumulating evidence and may already be past its \
deadline, you may run_escalation_sweep. The sweep applies campus policy \
itself, so do not try to reason about deadlines yourself.

When a report was left needing review, this is where your judgment matters \
most. Deduplication declined to place it and gave you its reasoning. Do not \
redo that comparison. Decide what to do about it:
- request_missing_information when one specific answer from the reporter would \
settle it, usually a floor or a room.
- merge_report when the evidence in front of you clearly supports one \
candidate and waiting would only delay the repair.
- create_new_incident when it plainly describes a separate problem.
- flag_for_human_review when the readings are genuinely balanced and a wrong \
guess costs more than the wait.

Prefer the action that gets work moving without discarding a real ambiguity. \
"Always ask a human" is not a policy; neither is guessing.

Use get_incident_state whenever you need to see what an incident actually \
looks like before deciding.

Finish with two or three sentences addressed to a facilities manager, saying \
what you decided and why. Name the specific evidence you relied on. Do not \
restate these instructions, do not mention tools by name, and do not describe \
yourself as an AI.\
"""


@lru_cache(maxsize=1)
def _runner():
    """Build the agent and runner once per process.

    Imported lazily so that importing this module never requires credentials
    or reaches the network.
    """
    _configure_backend()
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    agent = LlmAgent(
        name="incident_coordinator",
        model=get_settings().gemini_model,
        description="Decides what follow-up an incident needs after triage.",
        instruction=INSTRUCTION,
        tools=[
            get_incident_state,
            notify_team_priority_change,
            run_escalation_sweep,
            request_missing_information,
            merge_report,
            create_new_incident,
            flag_for_human_review,
        ],
    )
    return InMemoryRunner(agent=agent, app_name=APP_NAME)


def _situation(
    report_id: str,
    outcome: str,
    incident_id: str | None,
    previous_priority: str | None,
    new_priority: str | None,
    dedup_reasoning: str,
    evidence_count: int | None,
) -> str:
    """Describe what the pipeline just did, as the agent's opening context."""
    report = get_report(report_id)
    description = report.description if report else "(report unavailable)"

    lines = [
        "A report has just finished the intake pipeline.",
        "",
        f'Report {report_id}: "{description}"',
        f"Pipeline outcome: {outcome}",
    ]
    if incident_id:
        lines.append(f"Incident: {incident_id}")
        lines.append(f"Evidence on that incident: {evidence_count} report(s)")
    if previous_priority and new_priority:
        moved = "unchanged" if previous_priority == new_priority else "changed"
        lines.append(
            f"Priority {moved}: {previous_priority} -> {new_priority}"
        )
    lines += [
        "",
        "Why deduplication reached that outcome:",
        dedup_reasoning or "(no reasoning recorded)",
        "",
        "Decide what follow-up, if any, this warrants.",
    ]
    return "\n".join(lines)


async def coordinate(
    report_id: str,
    outcome: str,
    incident_id: str | None = None,
    previous_priority: str | None = None,
    new_priority: str | None = None,
    dedup_reasoning: str = "",
    evidence_count: int | None = None,
    campus_id: str | None = None,
) -> dict[str, Any]:
    """Run the coordinator over a finished pipeline result.

    Args:
        report_id: The report that just went through intake.
        outcome: ``new_incident``, ``merged``, or ``needs_review``.
        incident_id: Incident the report landed on, if any.
        previous_priority: Incident priority before this report arrived.
        new_priority: Incident priority after it.
        dedup_reasoning: The deduplication decision's own explanation, passed
            through so the agent does not repeat the comparison.
        evidence_count: Reports now linked to the incident.
        campus_id: Campus, for the decision record.

    Returns:
        A dict with ``actions`` (tool names the agent invoked, in order),
        ``reasoning`` (its explanation), ``decision_id``, and ``error`` --
        ``None`` on success, otherwise the exception that stopped it. Never
        raises: a coordinator failure must not fail a report that was already
        accepted and dispatched. It is always recorded, though, so a failure is
        visible in the trail rather than absent from it.
    """
    from google.genai import types

    settings = get_settings()
    session_id = f"coord-{report_id}"
    actions: list[str] = []
    said: list[str] = []
    failure: str | None = None
    trace: str | None = None

    try:
        runner = _runner()
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id="relay", session_id=session_id
        )
        prompt = _situation(
            report_id,
            outcome,
            incident_id,
            previous_priority,
            new_priority,
            dedup_reasoning,
            evidence_count,
        )
        async for event in runner.run_async(
            user_id="relay",
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if not (event.content and event.content.parts):
                continue
            for part in event.content.parts:
                if part.function_call:
                    actions.append(part.function_call.name)
                elif part.text:
                    said.append(part.text)
    except Exception as exc:  # noqa: BLE001 - follow-up must never fail intake
        # Still caught, because the report has already been triaged, placed,
        # and dispatched by this point and failing the request would discard
        # work that succeeded. What changed is that the failure is no longer
        # silent: it falls through to the same record_decision below as every
        # other outcome, so "the coordinator broke" and "the coordinator was
        # never called" stop looking identical in the trail. Previously this
        # returned here, ahead of the record, and a broken coordinator left no
        # evidence anywhere that it had run at all.
        logger.exception("Coordinator failed for report %s", report_id)
        failure = f"{type(exc).__name__}: {exc}"
        trace = traceback.format_exc()

    reasoning = " ".join(text.strip() for text in said if text.strip()).strip()

    # One record per invocation, whatever happened: the agent acted, judged
    # that nothing needed doing, or failed. "Nothing needed following up, and
    # here is why" is a decision a manager should be able to read, and a
    # failure is one an engineer must be able to find.
    decision = record_decision(
        Decision(
            campus_id=campus_id or settings.campus_id,
            decision_type=DecisionType.COORDINATION,
            decided_by=DecisionActor.AGENT,
            subject_type="incidents" if incident_id else "reports",
            subject_id=incident_id or report_id,
            outcome="error"
            if failure
            else (", ".join(actions) if actions else "no follow-up needed"),
            rationale=failure
            or reasoning
            or "The coordinator returned no explanation.",
            tool_name="incident_coordinator",
            model=settings.gemini_model,
            inputs={
                "report_id": report_id,
                "pipeline_outcome": outcome,
                "previous_priority": previous_priority,
                "new_priority": new_priority,
                "actions_taken": actions,
                # The stack trace goes in inputs rather than the rationale:
                # rationale is what a facilities manager reads, and this is for
                # whoever has to fix it. Firestore keeps it either way.
                **({"traceback": trace} if trace else {}),
            },
        )
    )

    if failure:
        logger.warning("Coordinator error recorded as %s: %s", decision.id, failure)
    else:
        logger.info(
            "Coordinator on %s (%s): %s",
            report_id,
            outcome,
            ", ".join(actions) if actions else "no action",
        )
    return {
        "actions": actions,
        "reasoning": reasoning,
        "decision_id": decision.id,
        "error": failure,
    }
