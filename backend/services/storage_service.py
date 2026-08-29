"""Cloud Storage helpers for report photos.

Photos are written under ``reports/{report_id}/{filename}`` in the configured
bucket. The bucket stays private; the frontend reads photos through short-lived
signed URLs rather than public objects.
"""

from __future__ import annotations

import logging
import mimetypes

from google.api_core import exceptions as gcloud_exceptions

from config import get_settings, get_storage_bucket

logger = logging.getLogger(__name__)

PHOTO_PREFIX = "reports"
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_PHOTO_BYTES = 10 * 1024 * 1024
FALLBACK_CONTENT_TYPE = "image/jpeg"


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


def _parse_gcs_uri(gcs_uri: str) -> str:
    """Return the object name from a ``gs://`` URI in the configured bucket.

    Args:
        gcs_uri: URI to parse.

    Returns:
        The object name, without the bucket prefix.

    Raises:
        ValueError: If the URI is malformed or names a different bucket.
            Refusing other buckets keeps a stored URI from being used to read
            arbitrary objects the service account can reach.
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Not a gs:// URI: {gcs_uri!r}.")

    bucket_name, _, object_name = gcs_uri[len("gs://") :].partition("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Malformed gs:// URI: {gcs_uri!r}.")

    expected = get_settings().storage_bucket
    if bucket_name != expected:
        raise ValueError(
            f"URI {gcs_uri!r} names bucket {bucket_name!r}, not the configured "
            f"bucket {expected!r}."
        )
    return object_name


def download_photo(gcs_uri: str) -> tuple[bytes, str]:
    """Download a stored photo for multimodal analysis.

    Args:
        gcs_uri: ``gs://`` URI of the photo.

    Returns:
        A ``(bytes, content_type)`` pair. The content type falls back to the
        extension, then to JPEG, since Gemini needs one and objects uploaded
        outside :func:`upload_report_photo` may not carry it.

    Raises:
        ValueError: If ``gcs_uri`` is not a URI in the configured bucket.
        FileNotFoundError: If the object does not exist.
    """
    object_name = _parse_gcs_uri(gcs_uri)
    blob = get_storage_bucket().blob(object_name)

    try:
        data = blob.download_as_bytes()
    except gcloud_exceptions.NotFound as exc:
        raise FileNotFoundError(f"No object at {gcs_uri!r}.") from exc

    content_type = (
        blob.content_type
        or mimetypes.guess_type(object_name)[0]
        or FALLBACK_CONTENT_TYPE
    )
    logger.debug("Downloaded %s (%d bytes, %s)", gcs_uri, len(data), content_type)
    return data, content_type


def delete_photo(gcs_uri: str) -> None:
    """Delete a stored photo, ignoring objects that are already gone."""
    raise NotImplementedError
