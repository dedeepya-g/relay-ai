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
from functools import lru_cache
from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

ResponseT = TypeVar("ResponseT", bound=BaseModel)

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_RETRIES = 2


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


def generate_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """Generate a plain-text completion.

    Args:
        prompt: User-turn prompt.
        system_instruction: Optional system instruction for the model.
        temperature: Sampling temperature; low by default because Relay's
            reasoning should be reproducible.

    Returns:
        The model's text response.

    Raises:
        GeminiError: If the call fails or returns no candidates.
    """
    raise NotImplementedError


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
            ``response_model`` after :data:`DEFAULT_MAX_RETRIES` attempts.
    """
    raise NotImplementedError


def embed_text(texts: list[str]) -> list[list[float]]:
    """Embed report descriptions for similarity-based duplicate shortlisting.

    Args:
        texts: Descriptions to embed.

    Returns:
        One embedding vector per input, in the same order.

    Raises:
        GeminiError: If the embedding call fails.
    """
    raise NotImplementedError


def describe_photo(image: tuple[bytes, str], prompt: str) -> dict[str, Any]:
    """Extract structured observations from a report photo.

    Args:
        image: ``(bytes, content_type)`` pair for the photo.
        prompt: Instruction describing what to look for, e.g. severity cues.

    Returns:
        Parsed observations to merge into the report's triage result.

    Raises:
        GeminiError: If the call fails or returns unusable output.
    """
    raise NotImplementedError
