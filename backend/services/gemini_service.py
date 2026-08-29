"""Thin wrapper around the Google GenAI SDK, backed by Vertex AI.

Centralizes model selection, retries, and structured-output parsing so agent
tools deal in typed Python objects instead of raw SDK responses.

The client runs in Vertex AI mode rather than AI Studio API-key mode: requests
are authorized by Application Default Credentials and billed to the project's
existing Google Cloud billing account, so no separate Gemini API key exists to
provision, rotate, or leak. Locally that means ``gcloud auth
application-default login``; on Cloud Run it means the runtime service account,
which needs the Vertex AI User role.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError

from config import get_settings

logger = logging.getLogger(__name__)

ResponseT = TypeVar("ResponseT", bound=BaseModel)

#: Zero for every reasoning call. Relay's model calls are classification and
#: comparison, not generation: the same report must yield the same category on
#: every run, or a demo cannot be replayed and an audit trail cannot be
#: defended. Sampling variation buys nothing here.
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.0

#: Status codes worth retrying. Everything else -- a bad request, an unknown
#: model, a permission failure -- fails the same way on every attempt, so
#: retrying only delays the error the caller needs to see.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class GeminiError(RuntimeError):
    """Raised when a Gemini call fails or returns unusable output."""


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    """Return the cached Vertex AI client.

    Constructed lazily so importing this module never requires credentials.
    The client is thread-safe and holds pooled connections, so it is built once
    per process rather than per request.
    """
    settings = get_settings()
    logger.debug(
        "Creating Vertex AI client (project=%s, location=%s)",
        settings.project_id,
        settings.gemini_location,
    )
    return genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.gemini_location,
    )


def _build_contents(prompt: str, image: tuple[bytes, str] | None) -> types.Content:
    """Assemble the user turn, placing the image before the text.

    Gemini attends to an image more reliably when it precedes the instructions
    that refer to it.
    """
    parts: list[types.Part] = []
    if image is not None:
        data, content_type = image
        parts.append(types.Part.from_bytes(data=data, mime_type=content_type))
    parts.append(types.Part.from_text(text=prompt))
    return types.Content(role="user", parts=parts)


def _parse(response: types.GenerateContentResponse, response_model: type[ResponseT]) -> ResponseT:
    """Extract a validated model from a response.

    Prefers the SDK's own parsing and falls back to validating the raw JSON
    text, which covers responses the SDK declines to parse.

    Raises:
        ValidationError: If the payload does not satisfy ``response_model``.
        GeminiError: If the response carries no usable payload at all.
    """
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, response_model):
        return parsed

    text = (response.text or "").strip()
    if not text:
        raise GeminiError(
            "Gemini returned an empty response; it may have been blocked by a "
            "safety filter or stopped early."
        )
    return response_model.model_validate_json(text)


def generate_structured(
    prompt: str,
    response_model: type[ResponseT],
    *,
    system_instruction: str | None = None,
    image: tuple[bytes, str] | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> ResponseT:
    """Generate a response constrained to a Pydantic schema.

    Every reasoning step in Relay -- triage, deduplication, prioritization,
    routing -- goes through this function so results arrive already validated.

    Args:
        prompt: User-turn prompt.
        response_model: Pydantic model describing the expected JSON shape.
        system_instruction: Optional system instruction for the model.
        image: Optional ``(bytes, content_type)`` pair to send alongside the
            prompt, used when a report includes a photo.
        temperature: Sampling temperature.

    Returns:
        A validated instance of ``response_model``.

    Raises:
        GeminiError: If the call fails, or the response cannot be parsed into
            ``response_model`` after :data:`DEFAULT_MAX_RETRIES` retries. Raw
            SDK exceptions never escape this function.
    """
    settings = get_settings()
    contents = _build_contents(prompt, image)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_model,
    )

    last_error: Exception | None = None
    for attempt in range(DEFAULT_MAX_RETRIES + 1):
        try:
            response = get_client().models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
            return _parse(response, response_model)
        except APIError as exc:
            if exc.code not in RETRYABLE_STATUS_CODES:
                raise GeminiError(
                    f"Gemini call failed with HTTP {exc.code} and will not be "
                    f"retried: {exc.message}"
                ) from exc
            last_error = exc
            logger.warning(
                "Gemini call failed with retryable HTTP %s (attempt %d/%d): %s",
                exc.code,
                attempt + 1,
                DEFAULT_MAX_RETRIES + 1,
                exc.message,
            )
        except (ValidationError, GeminiError) as exc:
            last_error = exc
            logger.warning(
                "Gemini returned an unusable %s payload (attempt %d/%d): %s",
                response_model.__name__,
                attempt + 1,
                DEFAULT_MAX_RETRIES + 1,
                exc,
            )

        if attempt < DEFAULT_MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))

    raise GeminiError(
        f"Gemini did not return a usable {response_model.__name__} after "
        f"{DEFAULT_MAX_RETRIES + 1} attempts: {last_error}"
    ) from last_error
