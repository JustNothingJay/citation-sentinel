"""
DOI validation — verify that each DOI resolves to a real publication.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import httpx


class ValidationStatus(str, Enum):
    PASSED = "passed"
    PAYWALL = "paywall"  # 403/406 — DOI exists, behind access control
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    doi: str
    status: ValidationStatus
    http_code: int | None = None
    final_url: str | None = None
    error: str | None = None


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def validate_doi(
    doi: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 15.0,
) -> ValidationResult:
    """Validate a single DOI by attempting to resolve it via doi.org.

    Classification:
      - 2xx/3xx → PASSED (DOI resolves)
      - 403/406 → PAYWALL (DOI exists, content access restricted)
      - 5xx/timeout → TIMEOUT or FAILED
    """
    url = f"https://doi.org/{doi}"
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            headers={"User-Agent": _BROWSER_UA},
            follow_redirects=True,
            timeout=timeout,
        )

    try:
        resp = client.get(url)
        code = resp.status_code

        if 200 <= code < 400:
            return ValidationResult(
                doi=doi,
                status=ValidationStatus.PASSED,
                http_code=code,
                final_url=str(resp.url),
            )
        if code in (403, 406):
            return ValidationResult(
                doi=doi,
                status=ValidationStatus.PAYWALL,
                http_code=code,
                final_url=str(resp.url),
                error="DOI exists — paywall/bot-block",
            )
        return ValidationResult(
            doi=doi,
            status=ValidationStatus.FAILED,
            http_code=code,
            error=f"HTTP {code}",
        )
    except httpx.TimeoutException:
        return ValidationResult(
            doi=doi,
            status=ValidationStatus.TIMEOUT,
            error="Request timed out",
        )
    except httpx.HTTPError as exc:
        return ValidationResult(
            doi=doi,
            status=ValidationStatus.FAILED,
            error=str(exc)[:200],
        )
    finally:
        if owns_client:
            client.close()


def validate_batch(
    dois: list[str],
    *,
    delay: float = 0.5,
    timeout: float = 15.0,
    progress_fn=None,
) -> dict[str, ValidationResult]:
    """Validate a batch of DOIs. Returns mapping of DOI → result."""
    results: dict[str, ValidationResult] = {}

    with httpx.Client(
        headers={"User-Agent": _BROWSER_UA},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        for i, doi in enumerate(dois):
            result = validate_doi(doi, client=client)
            results[doi] = result

            if progress_fn:
                progress_fn(i + 1, len(dois), doi, result)

            time.sleep(delay)

    return results
