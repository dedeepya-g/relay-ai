"""ADK tool: understand a raw facility report.

Triage is the first and narrowest stage of the pipeline. It answers "what is
this report about?" and nothing else: category, urgency signals, and what the
reporter left out. Priority, team, and SLA are campus policy and are decided
downstream from this output plus the campus configuration.

Keeping the split strict matters for the audit trail. When Relay explains why
an incident was routed somewhere, the observation ("the reporter said water was
spreading") and the judgment ("spreading water in this building is critical")
come from different steps and can be reviewed separately.
"""

from __future__ import annotations

import logging
from typing import Any

from models.campus_config import CampusConfig
from models.common import IssueCategory
from models.common import ReportStatus, utc_now
from models.report import Report
from models.triage import TriageResult
from services.firestore_service import get_campus_config, get_report, update_report
from services.gemini_service import GeminiError, generate_structured

logger = logging.getLogger(__name__)

_CATEGORY_GUIDE = {
    IssueCategory.PLUMBING: "water, leaks, drains, fixtures, supply lines",
    IssueCategory.ELECTRICAL: "wiring, outlets, lighting, breakers, power loss",
    IssueCategory.HVAC: "heating, cooling, ventilation, building automation",
    IssueCategory.ACCESS: "locks, keys, card readers, doors that will not secure",
    IssueCategory.ELEVATOR: "elevator faults and entrapments",
    IssueCategory.SAFETY: "fire safety equipment, blocked exits, hazards to people",
    IssueCategory.CUSTODIAL: "cleaning, spills, waste, restocking",
    IssueCategory.STRUCTURAL: "walls, ceilings, floors, windows, furniture, carpentry",
    IssueCategory.GROUNDS: "exterior grounds, walkways, landscaping, snow and ice",
    IssueCategory.PEST: "insects, rodents, other pests",
    IssueCategory.IT_AV: "projectors, displays, classroom audio-visual equipment",
    IssueCategory.OTHER: "anything that genuinely fits no category above",
}

SYSTEM_INSTRUCTION = f"""\
You are the classification stage of a university facilities triage system. You \
read one maintenance report and describe what it is about. You do not decide \
what should happen next.

You must NOT assign priority, choose a maintenance team, set a deadline, or \
recommend an action. A separate stage does that using campus policy you cannot \
see. Inventing policy here would silently override it.

Return exactly these fields.

issue_type -- the single category of the UNDERLYING FAULT. Choose only from \
this list; never invent a value:
{chr(10).join(f"  {c.value}: {d}" for c, d in _CATEGORY_GUIDE.items())}

Classify the fault, not what the fault threatens. Water from a failed pipe \
that is approaching an electrical outlet is a plumbing fault creating an \
electrical hazard: issue_type is plumbing, and the hazard belongs in \
severity_signals. Choosing the category of the threatened system would split \
reports about one physical problem across different teams.

severity_signals -- short phrases taken from the report that indicate urgency, \
spread, or danger. Quote the reporter's own wording rather than paraphrasing, \
so the record stays traceable to what was actually said.

Quote the MINIMAL meaningful phrase. Drop leading words that carry no urgency \
information: "water spreading", not "There is water spreading"; "getting close \
to an electrical outlet", not "Water is getting close to an electrical outlet".

A signal is an escalating or hazardous CONDITION, not the existence of a \
problem. Spreading, proximity to electrical or fire hazards, blocked exits, \
structural risk, and risk to people are signals. The fault itself never is. A \
report describing a contained, non-spreading, non-hazardous problem returns an \
empty list.

Worked example: "Water is leaking inside the third-floor restroom" describes a \
contained leak with no spread, no hazard proximity, and no urgency language, so \
severity_signals is []. The word "leaking" names the fault; it is not a signal \
on its own.

is_potential_emergency -- true only when the report describes genuine danger to \
people or damage actively getting worse. You will be given the campus emergency \
keyword list as a strong signal, but it is neither necessary nor sufficient: a \
report can be an emergency using none of those words, and a report can contain \
one harmlessly ("the fire extinguisher inspection tag is expired", "there is no \
smell of gas"). Judge the described situation, not the vocabulary.

missing_fields -- location details a dispatcher would need but does not have. \
Use only: building, floor, room.

Treat a field as present only when the report or photo gives an actual \
IDENTIFIER for it, never merely a clue about where to look. A room number \
counts. So does an unambiguously named space, where only one such room exists \
on that floor ("the third-floor women's restroom"). Directional and proximity \
wording does not count, however useful it is: "near the elevator", "toward the \
stairs", "down the hall from the chemistry lab" narrow a search without ever \
confirming which room, so room remains missing. Apply the same test to building \
and floor.

When a field is genuinely uncertain, list it. An unnecessary confirmation costs \
one question; an assumed location costs a crew sent to the wrong room.

confidence_note -- one sentence naming the specific uncertainty in your \
classification, or stating plainly that the report was unambiguous. Do not \
restate the report.

Report only what the text and photo support. If the report is vague, say so in \
confidence_note and classify conservatively rather than guessing at detail.\
"""


def _describe_location(report: Report) -> str:
    """Render the reporter-supplied location, naming what was left blank.

    Stating the gaps explicitly stops the model from treating an absent floor
    as an unstated one and quietly inferring a value.
    """
    location = report.location
    parts = [f"building_id: {location.building_id}"]
    parts.append(f"building_name: {location.building_name or '(not given)'}")
    parts.append(f"floor: {location.floor or '(not given)'}")
    parts.append(f"room: {location.room or '(not given)'}")
    if location.detail:
        parts.append(f"detail: {location.detail}")
    return "\n".join(f"  {part}" for part in parts)


def _build_prompt(
    report: Report, emergency_keywords: list[str], has_photo: bool
) -> str:
    """Assemble the user turn for one report.

    Campus emergency keywords are passed as reference data in the user turn
    rather than baked into the system instruction, so the instruction stays
    identical across campuses and the policy stays in the campus config.
    """
    keywords = ", ".join(emergency_keywords) if emergency_keywords else "(none configured)"
    photo_note = (
        "A photo taken by the reporter is attached. Use it to confirm or "
        "correct the text, and to fill in details the text omits."
        if has_photo
        else "No photo was attached. Classify from the text alone; do not "
        "speculate about what a photo might have shown."
    )

    return f"""\
Campus emergency keywords (strong signal, not a rule):
  {keywords}

Reporter-supplied location:
{_describe_location(report)}

Report text:
\"\"\"
{report.description}
\"\"\"

{photo_note}"""


def _load_photo(report: Report) -> tuple[bytes, str] | None:
    """Fetch the report's photo, or ``None`` if there is none or it is unusable.

    A photo is supporting evidence, never the substance of a report. Losing it
    degrades the classification; failing the report over it would lose the
    reporter's text as well, which is the part that matters.
    """
    if report.photo_uri is None:
        return None

    try:
        from services.storage_service import download_photo

        return download_photo(report.photo_uri)
    except Exception:  # noqa: BLE001 - any photo failure degrades to text-only
        logger.warning(
            "Could not read photo %s for report %s; analyzing text only.",
            report.photo_uri,
            report.id,
            exc_info=True,
        )
        return None


def analyze_report(
    report: Report, campus_config: CampusConfig | None = None
) -> TriageResult:
    """Extract structured observations from one report using Gemini.

    Classifies the report and surfaces urgency signals and gaps. It applies no
    campus policy: the returned :class:`~models.triage.TriageResult` says what
    was reported, and ``route_and_prioritize`` decides what to do about it.

    Args:
        report: The report to analyze. Its photo is included when one is
            attached and readable.
        campus_config: Campus configuration supplying the emergency keyword
            list. Fetched from Firestore when omitted; analysis proceeds
            without keywords if the campus has not been seeded.

    Returns:
        The structured triage result.

    Raises:
        GeminiError: If Gemini cannot produce a valid result after retries.
    """
    config = campus_config or get_campus_config(report.campus_id)
    if config is None:
        logger.warning(
            "No campus configuration for %s; triaging report %s without "
            "emergency keywords.",
            report.campus_id,
            report.id,
        )

    image = _load_photo(report)
    prompt = _build_prompt(
        report,
        emergency_keywords=config.emergency_keywords if config else [],
        has_photo=image is not None,
    )

    result = generate_structured(
        prompt,
        TriageResult,
        system_instruction=SYSTEM_INSTRUCTION,
        image=image,
    )
    logger.info(
        "Triaged report %s as %s (emergency=%s, %d signals)",
        report.id,
        result.issue_type.value,
        result.is_potential_emergency,
        len(result.severity_signals),
    )
    return result


def triage_report(report_id: str) -> dict[str, Any]:
    """Read a facility report and extract what it is actually about.

    Call this first for every new report, before looking for duplicates. Reads
    the report, combines the reporter's text with the attached photo if there
    is one, and stores the classification back onto the report so later steps
    and the audit trail can read it.

    Args:
        report_id: Id of the report to triage.

    Returns:
        A dict with keys ``report_id``, ``status``, ``issue_type``,
        ``severity_signals``, ``is_potential_emergency``, ``missing_fields``,
        and ``confidence_note``; or ``{"error": ...}`` if the report does not
        exist or could not be triaged.
    """
    report = get_report(report_id)
    if report is None:
        return {"error": f"No report {report_id!r}."}

    try:
        result = analyze_report(report)
    except GeminiError as exc:
        logger.exception("Triage failed for report %s", report_id)
        return {"error": f"Could not triage report {report_id!r}: {exc}"}

    update_report(
        report_id,
        {
            "triage": result.to_firestore(),
            "category": result.issue_type.value,
            "status": ReportStatus.TRIAGED.value,
            "triaged_at": utc_now(),
        },
    )

    return {
        "report_id": report_id,
        "status": ReportStatus.TRIAGED.value,
        "issue_type": result.issue_type.value,
        "severity_signals": result.severity_signals,
        "is_potential_emergency": result.is_potential_emergency,
        "missing_fields": [field.value for field in result.missing_fields],
        "confidence_note": result.confidence_note,
    }
