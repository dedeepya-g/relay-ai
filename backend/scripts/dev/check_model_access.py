"""Probe which Gemini model ids this project can actually call on Vertex AI.

DIAGNOSTIC TOOL -- not part of the running service. Nothing here is imported by
``main.py`` or by any agent tool, and it writes no files and mutates no state.

Model availability on Vertex AI depends on the project, the region, and the
model's launch stage, so the only reliable answer is an actual request. This
script sends a trivial prompt to every (model name, id format) combination and
reports the outcome, using the same client the service uses -- Vertex AI mode
authorized by Application Default Credentials.

Reading the results:

* HTTP 404 -- the id does not resolve; the model does not exist, is not served
  in this region, or the string is malformed.
* HTTP 429 -- the model exists and is permitted, but quota or billing blocked
  this request. Access is real; capacity is not.
* HTTP 403 -- the model exists but the caller lacks permission, which usually
  means a missing IAM role or an un-accepted model licence.
* HTTP 400 -- the request reached the model endpoint but was rejected, most
  often because the id is well-formed yet unsupported for this method.

Usage:
    cd backend
    python -m scripts.dev.check_model_access [--location us-central1] [--verbose]

Exits 0 if at least one combination succeeded, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass

from config import ConfigurationError, get_settings

PROBE_PROMPT = "Reply with the word OK and nothing else."

#: Candidate model names, ordered with the known-working control last so the
#: run ends on a reference point for comparison.
MODEL_NAMES: tuple[str, ...] = (
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
)

#: Vertex AI accepts a bare model id and a fully-qualified publisher path. The
#: two resolve differently often enough that both are worth probing.
ID_FORMATS: tuple[tuple[str, str], ...] = (
    ("short", "{name}"),
    ("full", "publishers/google/models/{name}"),
)

_MAX_REPLY_CHARS = 40
_MAX_ERROR_CHARS = 96


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Outcome of one generate_content call against one model id.

    Attributes:
        model_name: Bare model name under test.
        id_format: Which id format was used (``short`` or ``full``).
        model_id: The exact string passed to the API.
        succeeded: Whether the call returned a usable response.
        status: HTTP status code, or 0 when the failure was not an API error.
        reply: Text the model returned; empty on failure.
        error: One-line failure reason; empty on success.
        exception: The captured exception, printed only with ``--verbose``.
    """

    model_name: str
    id_format: str
    model_id: str
    succeeded: bool
    status: int = 0
    reply: str = ""
    error: str = ""
    exception: BaseException | None = None


def _status_of(exc: BaseException) -> int:
    """Return the HTTP status code carried by a GenAI SDK error, else 0.

    ``google.genai.errors.APIError`` exposes the status as ``code``; other
    exception types (transport, credential, argument errors) carry none.
    """
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else 0


def _summarize(exc: BaseException) -> str:
    """Reduce an exception to a single truncated line.

    Google client errors carry multi-line messages with embedded help links;
    only the leading text is useful in a results table.
    """
    message = getattr(exc, "message", None) or str(exc)
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    if not first_line:
        return type(exc).__name__
    if len(first_line) > _MAX_ERROR_CHARS:
        first_line = first_line[: _MAX_ERROR_CHARS - 1].rstrip() + "…"
    return first_line


def probe_model(client: object, model_name: str, id_format: str, model_id: str) -> ProbeResult:
    """Send the probe prompt to one model id and classify the outcome.

    Args:
        client: Vertex AI ``genai.Client`` used for the call.
        model_name: Bare model name under test, for reporting.
        id_format: Label of the id format under test, for reporting.
        model_id: The exact string to pass to the API.

    Returns:
        A :class:`ProbeResult` describing what happened. Never raises: every
        failure mode is data in the report.
    """
    try:
        response = client.models.generate_content(model=model_id, contents=PROBE_PROMPT)
    except Exception as exc:  # noqa: BLE001 - diagnostics report, never crash
        return ProbeResult(
            model_name=model_name,
            id_format=id_format,
            model_id=model_id,
            succeeded=False,
            status=_status_of(exc),
            error=_summarize(exc),
            exception=exc,
        )

    reply = (response.text or "").strip()
    if not reply:
        return ProbeResult(
            model_name=model_name,
            id_format=id_format,
            model_id=model_id,
            succeeded=False,
            status=200,
            error="Empty response (possibly blocked by a safety filter).",
        )
    if len(reply) > _MAX_REPLY_CHARS:
        reply = reply[: _MAX_REPLY_CHARS - 1].rstrip() + "…"
    return ProbeResult(
        model_name=model_name,
        id_format=id_format,
        model_id=model_id,
        succeeded=True,
        status=200,
        reply=reply,
    )


def run_probes(client: object) -> list[ProbeResult]:
    """Probe every (model name, id format) combination in declaration order."""
    return [
        probe_model(client, name, label, template.format(name=name))
        for name in MODEL_NAMES
        for label, template in ID_FORMATS
    ]


def _print_table(results: list[ProbeResult]) -> None:
    """Print the results as an aligned, scannable table."""
    id_width = max((len(r.model_id) for r in results), default=0)
    header = f"{'MODEL ID TRIED'.ljust(id_width)}  RESULT   CODE  DETAIL"
    print(header)
    print("-" * len(header))
    for result in results:
        verdict = "OK" if result.succeeded else "FAIL"
        code = str(result.status) if result.status else "-"
        detail = f"returned {result.reply!r}" if result.succeeded else result.error
        print(f"{result.model_id.ljust(id_width)}  {verdict.ljust(7)} {code.rjust(4)}  {detail}")


def _print_tracebacks(results: list[ProbeResult]) -> None:
    """Print full tracebacks for failures that captured an exception."""
    failures = [r for r in results if r.exception is not None]
    if not failures:
        return
    print()
    print("Tracebacks")
    print("=" * 72)
    for result in failures:
        print(f"\n--- {result.model_id} ---")
        traceback.print_exception(result.exception)


def _print_summary(results: list[ProbeResult]) -> None:
    """Print which model names are reachable and which ids to use."""
    print()
    print("=" * 72)
    working = [r for r in results if r.succeeded]
    print(f"{len(working)}/{len(results)} model ids responded")

    if not working:
        print("No model id succeeded. Nothing here is safe to configure.")
        return

    print()
    print("Usable model ids:")
    for name in MODEL_NAMES:
        usable = [r.model_id for r in working if r.model_name == name]
        if usable:
            print(f"  {name}: {', '.join(usable)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Probe which Gemini model ids this project can call on Vertex AI."
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Vertex AI region to probe. Defaults to RELAY_GEMINI_LOCATION.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full tracebacks for failed probes.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Probe every model id combination and print a results table.

    Returns:
        0 if at least one combination succeeded, 1 otherwise.
    """
    args = parse_args(argv)

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    location = args.location or settings.gemini_location

    try:
        from google import genai

        client = genai.Client(
            vertexai=True, project=settings.project_id, location=location
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics report, never crash
        print(f"Could not create the Vertex AI client: {_summarize(exc)}", file=sys.stderr)
        return 1

    print("Gemini model access probe")
    print("=" * 72)
    print(f"project:     {settings.project_id}")
    print(f"location:    {location}")
    print("credentials: Application Default Credentials (Vertex AI mode)")
    print(f"prompt:      {PROBE_PROMPT!r}")
    print("=" * 72)
    print()

    results = run_probes(client)
    _print_table(results)
    if args.verbose:
        _print_tracebacks(results)
    _print_summary(results)

    return 0 if any(r.succeeded for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
