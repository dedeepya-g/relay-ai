"""Cloud Storage helpers for report photos.

Photos are written under ``reports/{report_id}/{filename}`` in the configured
bucket. The bucket stays private; the frontend reads photos through short-lived
signed URLs rather than public objects.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PHOTO_PREFIX = "reports"
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_PHOTO_BYTES = 10 * 1024 * 1024


class PhotoRejectedError(ValueError):
    """Raised when an upload fails validation before it reaches the bucket."""


def upload_report_photo(
    report_id: str,
    data: bytes,
    content_type: str,
    filename: str | None = None,
) -> str:
    """Upload a report photo and return its ``gs://`` URI.

    Args:
        report_id: Report the photo belongs to; determines the object prefix.
        data: Raw image bytes.
        content_type: MIME type declared by the client.
        filename: Original filename, used for the object's extension. A name is
            generated when omitted.

    Returns:
        The ``gs://bucket/object`` URI of the stored photo.

    Raises:
        PhotoRejectedError: If the content type is unsupported or the payload
            exceeds :data:`MAX_PHOTO_BYTES`.
    """
    raise NotImplementedError


def generate_signed_url(gcs_uri: str, ttl_seconds: int | None = None) -> str:
    """Return a time-limited read URL for a stored photo.

    Args:
        gcs_uri: ``gs://`` URI returned by :func:`upload_report_photo`.
        ttl_seconds: Lifetime of the URL; defaults to the configured TTL.

    Raises:
        ValueError: If ``gcs_uri`` is not a ``gs://`` URI in the configured
            bucket.
    """
    raise NotImplementedError


def download_photo(gcs_uri: str) -> tuple[bytes, str]:
    """Download a stored photo for multimodal analysis.

    Args:
        gcs_uri: ``gs://`` URI of the photo.

    Returns:
        A ``(bytes, content_type)`` pair.

    Raises:
        FileNotFoundError: If the object does not exist.
    """
    raise NotImplementedError


def delete_photo(gcs_uri: str) -> None:
    """Delete a stored photo, ignoring objects that are already gone."""
    raise NotImplementedError
