# Relay-ai

Relay is an AI campus maintenance coordinator built with Gemini 3.5. It understands facility reports (photo, text, voice), detects duplicates, assigns priority, routes to the right team, and tracks issues to resolution, auto-escalating anything overdue. Built for All Things Agentic Hackathon (Taskmaster track).

## Vertex AI configuration note

Gemini 3.5 Flash is reached through Vertex AI with `location="global"`. It is not
served from individual regions: the same model id returns HTTP 404 against
`us-central1`, which reads like a missing-access error but is purely a region
availability issue. `backend/scripts/dev/check_model_access.py` probes model ids
against a given location and reports the distinction.

The Gemini endpoint location is independent of where the other services live —
Firestore and Cloud Storage remain in `us-east1`.
