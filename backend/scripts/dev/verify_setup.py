"""Preflight check for a local Relay development environment.

DIAGNOSTIC TOOL -- not part of the running service. Nothing here is imported by
``main.py`` or by any agent tool. Delete it once setup is confirmed, or keep it
for teammates onboarding onto the project.

Verifies the three external dependencies Relay needs:

1. Firestore  -- reachable with Application Default Credentials.
2. Cloud Storage -- the configured media bucket exists and is readable.
3. Vertex AI  -- the configured Gemini model responds, authorized by the same
                 credentials (no API key involved).

Usage:
    cd backend
    python -m scripts.dev.verify_setup [--verbose]

Exits 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass, field

from config import ConfigurationError, Settings, get_settings

GEMINI_PROBE_PROMPT = "Reply with the word OK and nothing else."

_PASS = "PASS"
_FAIL = "FAIL"


@dataclass
class CheckResult:
    """Outcome of a single environment check.

    Attributes:
        name: Human-readable check name.
        passed: Whether the check succeeded.
        detail: Lines of supporting context printed under the check.
        error: One-line failure reason; empty when the check passed.
        hint: Suggested next step shown on failure.
        exception: The captured exception, printed only with ``--verbose``.
    """

    name: str
    passed: bool = False
    detail: list[str] = field(default_factory=list)
    error: str = ""
    hint: str = ""
    exception: BaseException | None = None


def _summarize(exc: BaseException) -> str:
    """Reduce an exception to a single readable line.

    Google client errors carry multi-line messages with embedded help links;
    only the first line is useful in a pass/fail summary.
    """
    first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {first_line}" if first_line else type(exc).__name__


def check_firestore(settings: Settings) -> CheckResult:
    """Confirm Firestore is reachable in the configured project.

    Lists top-level collections, which succeeds on an empty database and so
    proves connectivity and permissions without writing anything.
    """
    result = CheckResult(name="Firestore")
    try:
        from config import get_firestore_client

        client = get_firestore_client()
        collection_ids = sorted(collection.id for collection in client.collections())

        result.passed = True
        result.detail.append(f"project:    {settings.project_id}")
        result.detail.append(f"database:   {settings.firestore_database}")
        result.detail.append(
            "collections: "
            + (", ".join(collection_ids) if collection_ids else "(none yet)")
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics report, never crash
        result.error = _summarize(exc)
        result.hint = (
            "Confirm the Firestore database exists in Native mode and that "
            "'gcloud auth application-default login' has been run."
        )
        result.exception = exc
    return result


def check_storage(settings: Settings) -> CheckResult:
    """Confirm the configured Cloud Storage bucket exists and is readable."""
    result = CheckResult(name="Cloud Storage")
    try:
        from config import get_storage_client

        bucket = get_storage_client().get_bucket(settings.storage_bucket)

        result.passed = True
        result.detail.append(f"bucket:     {bucket.name}")
        result.detail.append(f"location:   {bucket.location} ({bucket.location_type})")
        result.detail.append(f"class:      {bucket.storage_class}")
    except Exception as exc:  # noqa: BLE001 - diagnostics report, never crash
        result.error = _summarize(exc)
        result.hint = (
            f"Confirm bucket '{settings.storage_bucket}' exists in project "
            f"'{settings.project_id}' and that RELAY_STORAGE_BUCKET matches it."
        )
        result.exception = exc
    return result


def check_gemini(settings: Settings) -> CheckResult:
    """Confirm Gemini responds through Vertex AI on the project's credentials.

    Sends a trivial prompt through the same client factory the service uses, so
    a pass here means the real code path works: Vertex AI mode, Application
    Default Credentials, and the configured model and region.
    """
    result = CheckResult(name="Vertex AI (Gemini)")
    result.detail.append(f"model:      {settings.gemini_model}")
    result.detail.append(f"location:   {settings.gemini_location}")

    try:
        from services.gemini_service import get_client

        response = get_client().models.generate_content(
            model=settings.gemini_model, contents=GEMINI_PROBE_PROMPT
        )
        reply = (response.text or "").strip()

        result.passed = bool(reply)
        result.detail.append(f"reply:      {reply!r}")
        if not result.passed:
            result.error = "Model returned an empty response."
            result.hint = "Check whether the response was blocked by a safety filter."
    except Exception as exc:  # noqa: BLE001 - diagnostics report, never crash
        result.error = _summarize(exc)
        result.hint = (
            "Confirm the Vertex AI API is enabled "
            "('gcloud services enable aiplatform.googleapis.com'), that the "
            "credentials hold the Vertex AI User role, and that model "
            f"'{settings.gemini_model}' is served in {settings.gemini_location}."
        )
        result.exception = exc
    return result


def _print_result(result: CheckResult, verbose: bool) -> None:
    """Print one check's outcome in a fixed-width, scannable format."""
    status = _PASS if result.passed else _FAIL
    print(f"[{status}] {result.name}")
    for line in result.detail:
        print(f"       {line}")
    if not result.passed:
        print(f"       error:      {result.error}")
        if result.hint:
            print(f"       fix:        {result.hint}")
        if verbose and result.exception is not None:
            print()
            traceback.print_exception(result.exception)
    print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify local Firestore, Cloud Storage, and Gemini access."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full tracebacks for failed checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run every check and report a summary.

    Returns:
        0 if all checks passed, 1 if any failed or configuration is invalid.
    """
    args = parse_args(argv)

    print("Relay environment verification")
    print("=" * 62)

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"[{_FAIL}] Configuration\n       error:      {exc}\n")
        return 1

    print(f"       project:    {settings.project_id}")
    print("       credentials: Application Default Credentials (gcloud)")
    print("       gemini:     Vertex AI mode (no API key)")
    print("=" * 62)
    print()

    results = [
        check_firestore(settings),
        check_storage(settings),
        check_gemini(settings),
    ]
    for result in results:
        _print_result(result, verbose=args.verbose)

    passed = sum(1 for result in results if result.passed)
    print("=" * 62)
    print(f"{passed}/{len(results)} checks passed")
    if passed != len(results):
        failed = ", ".join(r.name for r in results if not r.passed)
        print(f"Failed: {failed}")
        if not args.verbose:
            print("Re-run with --verbose for full tracebacks.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
