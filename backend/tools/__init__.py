"""ADK tool functions the Relay agent can call.

Each module exposes exactly one tool. Tool docstrings are read by the model to
decide when to call them, so they describe *when* to use the tool as well as
what it does. Every tool returns a JSON-serializable dict and reports failures
in that dict rather than raising, so a single bad call cannot end the run.
"""

from tools.assign_priority import assign_priority
from tools.create_work_order import create_work_order
from tools.escalate_overdue_incidents import escalate_overdue_incidents
from tools.find_duplicate_incident import find_duplicate_incident
from tools.merge_report_into_incident import merge_report_into_incident
from tools.open_incident import open_incident
from tools.resolve_review import resolve_review
from tools.route_to_team import route_to_team
from tools.triage_report import triage_report
from tools.update_incident_status import update_incident_status

__all__ = [
    "assign_priority",
    "create_work_order",
    "escalate_overdue_incidents",
    "find_duplicate_incident",
    "merge_report_into_incident",
    "open_incident",
    "resolve_review",
    "route_to_team",
    "triage_report",
    "update_incident_status",
]
