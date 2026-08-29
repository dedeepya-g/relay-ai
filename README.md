# Relay-ai

Relay is an AI campus facilities coordination agent for "Relay University," a
fictional demo campus. It reads a facility report written in plain language,
classifies it, detects when several reports describe the same underlying
problem and merges them into a single incident, then assigns priority, routes
the incident to the maintenance team that owns it, and dispatches a work order.
An incident left unresolved past its deadline is escalated on a sweep. Every
decision is recorded with its reasoning.

Built with Gemini 3.5 on Vertex AI for the All Things Agentic Hackathon
(Taskmaster track).

## Status

Built and tested end to end: report classification, duplicate detection with a
human-review path for ambiguous cases, deterministic priority and SLA
derivation, routing to the owning team, work order dispatch, and an overdue
sweep that escalates a breached incident until it reaches the campus policy's
maximum level. Triage is multimodal: a photo already stored for a report is
analyzed alongside its text, though nothing stores one yet, so that path is not
reachable through the API.

The pipeline is reachable over HTTP and through a React operations dashboard:
report intake with cascading location selection, an incident queue that sorts a
"needs your attention" band above the rest of the board, incident detail
carrying the full decision trail, and the resolution action for a report Relay
paused. These endpoints were exercised with `curl` against a running server,
reproducing the pipeline tests exactly:

- `POST /reports` submits a report and runs it through the full pipeline,
  returning the outcome, priority, team, and the reasoning behind each.
- `GET /incidents` lists incidents that are still live work.
- `GET /incidents/{id}` returns one incident with its linked reports and its
  decision trail, each entry recording whether an agent or a person decided it
  and which model, if any, produced the judgment.
- `POST /reports/{id}/resolve` applies a person's decision to a report Relay
  paused for review.
- `GET /campus` serves the buildings, floors, rooms, and teams a client needs
  to submit and label reports, read from the seeded configuration.
- `GET /reviews` lists reports Relay declined to place, each with the reasoning
  that paused it.
- `POST /admin/check-overdue` runs one pass of the overdue sweep. Relay is meant
  to run this on a schedule; the endpoint calls the same function a scheduler
  would, with no shortcut for being triggered by hand.

Not yet implemented:

- Photo upload, signed-URL serving, and deletion (`upload_report_photo`,
  `generate_signed_url`, `delete_photo`). A photo sent to `POST /reports` is
  accepted and discarded: it is neither stored nor analyzed, and the response
  reports `photo_stored: false` rather than implying otherwise.
- Voice intake. `ReportSource.VOICE` is an unused enum value.

## How Relay reasons

Relay's demo scenario is one water leak in Harlow Science Center reported by
five different people. All five merge into a single incident, and the
incident's priority climbs as independent evidence accumulates:

| Report | Evidence | Reports describing danger | Priority |
| --- | --- | --- | --- |
| 1. Leak in the third-floor restroom | 1 | 0 | `low` |
| 2. Bathroom floor upstairs covered in water | 2 | 1 | `high` |
| 3. Water spreading toward the elevator | 3 | 2 | `critical` |
| 4. Men's restroom sink may have burst | 4 | 2 | `critical` |
| 5. Water close to an electrical outlet, floor 2 | 5 | 3 | `critical` |

Priority is driven by independent accounts of danger, not by report count
alone. It reaches `critical` at report 3, when a second person independently
describes a worsening condition, and then holds. Reports 4 and 5 add
corroboration without inflating anything, because there is nowhere justified
above `critical` to go. Nothing in the scenario is a scripted trigger: no
single report unlocks a level.

Report 4 is the clearest evidence of that calibration. "The men's restroom sink
may have burst" is classified as a potential emergency, but it quotes no
condition -- the reporter is speculating about a cause, not describing
something getting worse. Raising priority requires both the emergency flag and
a severity signal, so report 4 increases the evidence count without counting as
a danger report. Relay declines to escalate on a hunch.

Report 5 is the clearest evidence of the deduplication engine. It is on a
different floor from the leak and names an electrical hazard the original
report never mentioned, and it still merges into the same incident, because
water travelling downward is one fault seen from a second vantage point rather
than a second fault.

### Where the model's judgment enters, and where it does not

Gemini is used in exactly two places: classifying a report, and deciding
whether two reports describe the same underlying problem. Both are genuine
judgments about ambiguous natural language, and both can decline -- triage
records its uncertainty, and deduplication can return `needs_review`, which
pauses a report for a person instead of guessing.

Everything downstream is deterministic rule application over that output.
Priority, routing, and the overdue sweep read the campus configuration and the
accumulated evidence, and record their reasoning in the audit trail with
`model=None`, marking them as rule-based rather than model-derived. Whether a
deadline passed is arithmetic, and who gets told was written down in advance;
neither is a judgment. The same
evidence always produces the same priority and the same team, which is what
makes an escalation defensible when someone asks why a work order jumped the
queue.

## Vertex AI configuration note

Gemini 3.5 Flash is reached through Vertex AI with `location="global"`. It is not
served from individual regions: the same model id returns HTTP 404 against
`us-central1`, which reads like a missing-access error but is purely a region
availability issue. `backend/scripts/dev/check_model_access.py` probes model ids
against a given location and reports the distinction.

The Gemini endpoint location is independent of where the other services live —
Firestore and Cloud Storage remain in `us-east1`.
