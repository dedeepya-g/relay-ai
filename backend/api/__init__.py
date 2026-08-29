"""HTTP layer: request and response schemas, and the FastAPI routes.

Kept deliberately thin. Every route is wiring over a tool that is already
implemented and tested; no decision logic lives here, so the behaviour the API
exposes is the behaviour the pipeline tests already cover.
"""
