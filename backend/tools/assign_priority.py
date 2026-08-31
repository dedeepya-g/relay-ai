"""ADK tool: set an incident's priority and SLA deadline.

Priority is decided by rule, not by a model. The inputs it weighs -- how many
people reported the problem, whether any of them described danger, what
urgency signals they used -- were already extracted by triage, and turning
those into a level is campus policy rather than a judgment. A rule also means
the same evidence always produces the same priority, which is what makes an
escalation defensible when someone asks why a work order jumped the queue.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from models.campus_config import CampusConfig
from models.common import DecisionActor, DecisionType, Priority
from models.decision import Decision
from models.incident import Incident
from models.report import Report
from services.firestore_service import (
    get_campus_config,
    get_incident,
    list_reports_for_incident,
    record_decision,
    update_incident,
)

logger = logging.getLogger(__name__)

#: Lowest to highest. Every rule can only raise the level, never lower it, so
#: the outcome does not depend on which order the rules are evaluated in.
PRIORITY_ORDER: tuple[Priority, ...] = (
    Priority.LOW,
    Priority.MEDIUM,
    Priority.HIGH,
    Priority.CRITICAL,
)

#: Reports corroborating one problem. Independent accounts are evidence in
#: their own right: five people reporting one leak means it is affecting five
#: people's day, whatever words any single one of them used.
CORROBORATION_FOR_MEDIUM = 2
CORROBORATION_FOR_HIGH = 4

#: Reports that both describe danger and quote a condition supporting it. One
#: is enough to be urgent; two independent accounts of danger is a campus
#: emergency, not a maintenance queue item.
EMERGENCIES_FOR_HIGH = 1
EMERGENCIES_FOR_CRITICAL = 2


def _raise_to(current: Priority, target: Priority) -> Priority:
    """Return the higher of two priorities."""
    return max(current, target, key=PRIORITY_ORDER.index)


def _is_emergency_evidence(report: Report) -> bool:
    """Whether a report describes danger and quotes something supporting it.

    Both halves are required. The flag alone can be set on a report whose text
    turned out to be vague, and signals alone describe a problem without
    asserting danger; together they are a reporter saying something is wrong
    and pointing at why.
    """
    triage = report.triage
    return bool(
        triage and triage.is_potential_emergency and triage.severity_signals
    )


def evaluate_priority(reports: list[Report]) -> tuple[Priority, list[str]]:
    """Compute a priority from the evidence linked to an incident.

    Args:
        reports: Every report merged into the incident.

    Returns:
        The priority, and the reasons that raised it, in the order applied.
        The reasons are the audit trail: they say which evidence mattered, not
        merely what the answer was.
    """
    priority = Priority.LOW
    reasons: list[str] = []

    evidence_count = len(reports)
    emergencies = [report for report in reports if _is_emergency_evidence(report)]
    signals = [
        signal
        for report in reports
        if report.triage
        for signal in report.triage.severity_signals
    ]

    if signals:
        priority = _raise_to(priority, Priority.MEDIUM)
        reasons.append(
            f"{len(signals)} urgency signal(s) reported: "
            + "; ".join(f'"{signal}"' for signal in signals[:4])
        )
    if evidence_count >= CORROBORATION_FOR_MEDIUM:
        priority = _raise_to(priority, Priority.MEDIUM)
        reasons.append(
            f"{evidence_count} separate reports describe this problem"
        )
    if evidence_count >= CORROBORATION_FOR_HIGH:
        priority = _raise_to(priority, Priority.HIGH)
        reasons.append(
            f"corroboration reached {evidence_count} reports, which raises "
            "urgency on its own"
        )
    if len(emergencies) >= EMERGENCIES_FOR_HIGH:
        priority = _raise_to(priority, Priority.HIGH)
        reasons.append(
            f"{len(emergencies)} report(s) describe conditions posing danger"
        )
    if len(emergencies) >= EMERGENCIES_FOR_CRITICAL:
        priority = _raise_to(priority, Priority.CRITICAL)
        reasons.append(
            "multiple independent reports describe danger, not one person's "
            "impression"
        )

    if not reasons:
        plural = "report" if evidence_count == 1 else "reports"
        reasons.append(f"{evidence_count} {plural} with no urgency signals")
    return priority, reasons


def _sla_due_at(incident: Incident, priority: Priority, config: CampusConfig):
    """Derive the SLA deadline for a priority, measured from the incident's start.

    Measured from ``created_at`` rather than from now, because the clock a
    campus cares about started when the problem was first reported. Raising an
    incident's priority can therefore make it immediately overdue, which is the
    correct reading: the work should already have been done.
    """
    minutes = config.sla_minutes.get(priority)
    if minutes is None:
        return None
    return incident.created_at + timedelta(minutes=minutes)


#: How each level translates into what a coordinator should do about it. The
#: entry headline already names the level, so this says what it means rather
#: than repeating the word.
_CONSEQUENCE = {
    Priority.CRITICAL: "Needs someone now.",
    Priority.HIGH: "Should be picked up soon.",
    Priority.MEDIUM: "Worth attention, not urgent yet.",
    Priority.LOW: "Can wait for the next round.",
}


def explain_priority(priority: Priority, reports: list[Report]) -> str:
    """Say why this level, the way a coordinator would say it.

    The counted-out computation stays in the decision's ``inputs`` for audit;
    what gets read is the reason, not the arithmetic. "Priority medium because
    1 urgency signal(s) reported" describes the machine's working. "Water is
    pooling. Worth attention, not urgent yet." describes the situation.
    """
    signals = [
        signal
        for report in reports
        if report.triage
        for signal in report.triage.severity_signals
    ]
    dangerous = [
        report
        for report in reports
        if report.triage and report.triage.is_potential_emergency
    ]
    count = len(reports)

    if dangerous:
        who = "Several people describe" if len(dangerous) > 1 else "Someone describes"
        lead = f"{who} this as dangerous"
        lead = f"{lead}: {signals[0]}." if signals else f"{lead}."
    elif signals:
        first = signals[0]
        lead = f"{first[0].upper()}{first[1:]}."
    else:
        lead = "Nothing reported so far describes spread or danger."

    if count >= 4:
        corroboration = f" {count} people have reported it, which counts on its own."
    elif count > 1:
        corroboration = f" {count} people have reported it."
    else:
        corroboration = ""

    return f"{lead}{corroboration} {_CONSEQUENCE[priority]}"


def assign_priority(incident_id: str) -> dict[str, Any]:
    """Assign a priority to an incident and derive its SLA deadline.

    Call this when an incident is opened and again whenever new evidence
    arrives, since corroboration alone can raise the level. Weighs how many
    reports describe the problem, how many describe danger, and what urgency
    signals they used, then applies the campus SLA policy for the result.

    The level is recomputed from all linked evidence on every call rather than
    adjusted from the last one, so re-running on unchanged evidence returns the
    same answer. Within one evaluation the rules only raise, never lower, which
    is why their order does not matter. Across calls the computed level
    replaces whatever was stored, including the model's default of medium on a
    freshly opened incident -- and, once a manual override exists, it would
    replace that too.

    Args:
        incident_id: Id of the incident to prioritize.

    Returns:
        A dict with ``incident_id``, ``priority``, ``previous_priority``,
        ``changed``, ``sla_due_at``, ``evidence_count``, and ``rationale``; or
        ``{"error": ...}`` if the incident or campus configuration is missing.
    """
    incident = get_incident(incident_id)
    if incident is None:
        return {"error": f"No incident {incident_id!r}."}
    config = get_campus_config(incident.campus_id)
    if config is None:
        return {
            "error": f"No campus configuration for {incident.campus_id!r}; "
            "SLA policy is unavailable."
        }

    reports = list_reports_for_incident(incident_id)
    priority, reasons = evaluate_priority(reports)
    rationale = explain_priority(priority, reports)
    due_at = _sla_due_at(incident, priority, config)

    updated = update_incident(
        incident_id, {"priority": priority.value, "sla_due_at": due_at}
    )
    record_decision(
        Decision(
            campus_id=incident.campus_id,
            decision_type=DecisionType.PRIORITIZATION,
            decided_by=DecisionActor.RULE,
            subject_type="incidents",
            subject_id=incident_id,
            outcome=f"priority {priority.value}",
            rationale=rationale,
            tool_name="assign_priority",
            model=None,
            inputs={
                "evidence_count": len(reports),
                "report_ids": [report.id for report in reports],
                "previous_priority": incident.priority.value,
            },
        )
    )

    return {
        "incident_id": incident_id,
        "priority": priority.value,
        "previous_priority": incident.priority.value,
        "changed": priority is not incident.priority,
        "sla_due_at": updated.sla_due_at.isoformat() if updated.sla_due_at else None,
        "evidence_count": len(reports),
        "rationale": rationale,
    }
