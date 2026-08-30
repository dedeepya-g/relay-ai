"""Cloud Storage helpers for report photos.

Photos are written under ``reports/{report_id}/{filename}`` in the configured
bucket. The bucket stays private; the frontend reads photos through short-lived
signed URLs rather than public objects.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from datetime import timedelta

import google.auth
import google.auth.transport.requests
from google.api_core import exceptions as gcloud_exceptions
from google.auth import impersonated_credentials

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
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise PhotoRejectedError(
            f"Unsupported content type {content_type!r}; expected one of "
            f"{sorted(ALLOWED_CONTENT_TYPES)}."
        )
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoRejectedError(
            f"Photo is {len(data)} bytes, over the {MAX_PHOTO_BYTES} byte limit."
        )

    extension = mimetypes.guess_extension(content_type) or ".jpg"
    object_name = f"{PHOTO_PREFIX}/{report_id}/{uuid.uuid4().hex}{extension}"

    blob = get_storage_bucket().blob(object_name)
    blob.upload_from_string(data, content_type=content_type)

    gcs_uri = f"gs://{get_settings().storage_bucket}/{object_name}"
    logger.info("Stored photo for report %s at %s", report_id, gcs_uri)
    return gcs_uri


def generate_signed_url(gcs_uri: str, ttl_seconds: int | None = None) -> str:
    """Return a time-limited read URL for a stored photo.

    Args:
        gcs_uri: ``gs://`` URI returned by :func:`upload_report_photo`.
        ttl_seconds: Lifetime of the URL; defaults to the configured TTL.

    Raises:
        ValueError: If ``gcs_uri`` is not a ``gs://`` URI in the configured
            bucket.
    """
    object_name = _parse_gcs_uri(gcs_uri)
    blob = get_storage_bucket().blob(object_name)
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().signed_url_ttl_seconds

    try:
        return blob.generate_signed_url(
            version="v4", expiration=timedelta(seconds=ttl), method="GET"
        )
    except AttributeError:
        # The runtime's own credentials (Cloud Run's attached service account,
        # or any metadata-server credential) carry no private key to sign
        # with directly. Self-impersonating through the IAM Credentials API
        # signs on its behalf instead -- it only works if that identity holds
        # Service Account Token Creator on itself, and re-raises otherwise so
        # a genuinely unsigned environment (e.g. local user credentials) fails
        # the same way it always did.
        source_credentials, _ = google.auth.default()
        # `service_account_email` reads back the literal string "default"
        # until the credentials have actually talked to the metadata server
        # once; refreshing first is what makes the real address available.
        source_credentials.refresh(google.auth.transport.requests.Request())
        service_account_email = getattr(
            source_credentials, "service_account_email", None
        )
        if not service_account_email or service_account_email == "default":
            raise
        signing_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=service_account_email,
            target_scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
            lifetime=min(ttl, 3600),
        )
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=ttl),
            method="GET",
            credentials=signing_credentials,
        )


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
    object_name = _parse_gcs_uri(gcs_uri)
    blob = get_storage_bucket().blob(object_name)
    try:
        blob.delete()
    except gcloud_exceptions.NotFound:
        pass
