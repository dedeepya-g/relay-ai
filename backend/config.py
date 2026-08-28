"""Environment configuration and Google Cloud client factories.

Settings are read once from the process environment (with ``backend/.env``
layered in for local development) and exposed through :func:`get_settings`.
Cloud clients are created lazily and cached so that importing this module never
requires credentials -- unit tests and tooling can import the package freely.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import firestore, storage

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parent / ".env"

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_FIRESTORE_DATABASE = "(default)"
DEFAULT_CAMPUS_ID = "relay-university"
DEFAULT_SIGNED_URL_TTL_SECONDS = 3600


class ConfigurationError(RuntimeError):
    """Raised when a required environment variable is missing or malformed."""


def _required(name: str) -> str:
    """Return the value of a required environment variable.

    Args:
        name: Environment variable name.

    Returns:
        The variable's value with surrounding whitespace stripped.

    Raises:
        ConfigurationError: If the variable is unset or empty.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Missing required environment variable {name!r}. "
            "See backend/.env.example for the full list."
        )
    return value


def _optional(name: str, default: str) -> str:
    """Return an optional environment variable, falling back to ``default``."""
    value = os.getenv(name, "").strip()
    return value or default


def _optional_int(name: str, default: int) -> int:
    """Return an optional integer environment variable.

    Raises:
        ConfigurationError: If the variable is set but is not an integer.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"Environment variable {name!r} must be an integer, got {raw!r}."
        ) from exc


def _optional_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Return an optional comma-separated environment variable as a tuple."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable snapshot of the runtime configuration.

    Attributes:
        project_id: Google Cloud project owning Firestore and Cloud Storage.
        gemini_api_key: API key used by the Google GenAI SDK.
        gemini_model: Gemini model id used for all reasoning calls.
        firestore_database: Firestore database id.
        storage_bucket: Cloud Storage bucket holding report photos.
        campus_id: Campus configuration document driving routing and SLAs.
        environment: Deployment environment (``local``/``staging``/``production``).
        log_level: Root logger level.
        allowed_origins: Browser origins permitted by the CORS middleware.
        signed_url_ttl_seconds: Lifetime of signed photo URLs.
    """

    project_id: str
    gemini_api_key: str
    gemini_model: str
    firestore_database: str
    storage_bucket: str
    campus_id: str
    environment: str
    log_level: str
    allowed_origins: tuple[str, ...]
    signed_url_ttl_seconds: int

    @property
    def is_production(self) -> bool:
        """Whether the service is running in the production environment."""
        return self.environment == "production"

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment.

        Raises:
            ConfigurationError: If a required variable is missing or malformed.
        """
        return cls(
            project_id=_required("GOOGLE_CLOUD_PROJECT"),
            gemini_api_key=_required("GEMINI_API_KEY"),
            gemini_model=_optional("RELAY_GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            firestore_database=_optional(
                "RELAY_FIRESTORE_DATABASE", DEFAULT_FIRESTORE_DATABASE
            ),
            storage_bucket=_required("RELAY_STORAGE_BUCKET"),
            campus_id=_optional("RELAY_CAMPUS_ID", DEFAULT_CAMPUS_ID),
            environment=_optional("RELAY_ENVIRONMENT", "local").lower(),
            log_level=_optional("RELAY_LOG_LEVEL", "INFO").upper(),
            allowed_origins=_optional_csv(
                "RELAY_ALLOWED_ORIGINS", ("http://localhost:5173",)
            ),
            signed_url_ttl_seconds=_optional_int(
                "RELAY_SIGNED_URL_TTL_SECONDS", DEFAULT_SIGNED_URL_TTL_SECONDS
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide settings, loading ``.env`` on first call.

    Values already present in the environment win over ``.env`` entries, which
    is what Cloud Run needs: the container has no ``.env`` file and reads its
    configuration from the service's environment variables.
    """
    load_dotenv(_ENV_FILE, override=False)
    settings = Settings.from_env()
    logger.info(
        "Loaded Relay settings (project=%s, environment=%s, model=%s)",
        settings.project_id,
        settings.environment,
        settings.gemini_model,
    )
    return settings


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    """Return the cached Firestore client.

    Credentials resolve through Application Default Credentials: the Cloud Run
    runtime service account in deployed environments, or
    ``GOOGLE_APPLICATION_CREDENTIALS`` / ``gcloud auth`` locally.
    """
    settings = get_settings()
    return firestore.Client(
        project=settings.project_id, database=settings.firestore_database
    )


@lru_cache(maxsize=1)
def get_storage_client() -> storage.Client:
    """Return the cached Cloud Storage client."""
    return storage.Client(project=get_settings().project_id)


@lru_cache(maxsize=1)
def get_storage_bucket() -> storage.Bucket:
    """Return the cached bucket handle for report photos.

    The handle is constructed without a network round trip; a missing bucket
    surfaces as an error on first read or write.
    """
    return get_storage_client().bucket(get_settings().storage_bucket)


def configure_logging() -> None:
    """Configure root logging for the configured log level.

    Cloud Run captures stdout and stderr, so plain stream logging is enough for
    log entries to reach Cloud Logging.
    """
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        force=True,
    )
