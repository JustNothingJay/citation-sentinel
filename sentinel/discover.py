"""
DOI discovery via the CrossRef API.

Uses the free, public CrossRef REST API with polite-pool headers.
No API key required — just a mailto address for rate-limit courtesy.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

from .extract import Reference, first_author_surname

# Default polite-pool contact
_DEFAULT_MAILTO = "citation-sentinel@example.com"

# CrossRef API base
_API = "https://api.crossref.org/works"


@dataclass
class CrossRefMatch:
    """Result of a CrossRef lookup."""

    found: bool = False
    doi: str | None = None
    title: str | None = None
    authors: str | None = None
    year: str | None = None
    score: float = 0.0
    quality: str = "none"  # good | partial | poor | none
    strategy: str | None = None
    container: str | None = None
    work_type: str | None = None


def _title_similarity(a: str, b: str) -> float:
    """Word-overlap similarity between two titles (3+ char words)."""
    if not a or not b:
        return 0.0
    wa = set(re.findall(r"\w{3,}", a.lower()))
    wb = set(re.findall(r"\w{3,}", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _extract_year(item: dict) -> str:
    """Best-effort year from a CrossRef work item."""
    for field in ("published-print", "published-online", "issued"):
        dp = item.get(field, {}).get("date-parts", [[]])
        if dp and dp[0] and dp[0][0]:
            return str(dp[0][0])
    return ""


def _extract_authors(item: dict, limit: int = 3) -> str:
    """Comma-separated surnames from a CrossRef work item."""
    authors = item.get("author", [])
    return ", ".join(a.get("family", "") for a in authors[:limit])


def _score_match(
    ref: Reference,
    item: dict,
    surname: str,
) -> tuple[float, dict]:
    """Score a CrossRef item against a reference. Returns (score, details)."""
    item_title_raw = ""
    titles = item.get("title", [])
    if isinstance(titles, list) and titles:
        item_title_raw = titles[0]
    elif isinstance(titles, str):
        item_title_raw = titles
    item_title = re.sub(r"<[^>]+>", "", item_title_raw)

    sim = _title_similarity(ref.title or "", item_title)

    item_authors = _extract_authors(item)
    if surname and surname.lower() in item_authors.lower():
        sim += 0.15

    item_year = _extract_year(item)
    if ref.year and item_year == str(ref.year):
        sim += 0.10

    # Journal match bonus
    container = ""
    ct = item.get("container-title")
    if isinstance(ct, list) and ct:
        container = ct[0]
    elif isinstance(ct, str):
        container = ct
    if ref.journal and container:
        j_sim = _title_similarity(ref.journal, container)
        if j_sim > 0.5:
            sim += 0.10

    details = {
        "title": item_title[:150],
        "authors": item_authors,
        "year": item_year,
        "doi": item.get("DOI", ""),
        "type": item.get("type", ""),
        "container": container,
    }
    return sim, details


def _query_crossref(
    client: httpx.Client,
    params: dict,
    rows: int = 3,
) -> list[dict]:
    """Execute a CrossRef API query. Returns work items."""
    params["rows"] = str(rows)
    try:
        resp = client.get(_API, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("items", [])
    except (httpx.HTTPError, ValueError, KeyError):
        return []


def discover_doi(
    ref: Reference,
    *,
    client: httpx.Client | None = None,
    mailto: str = _DEFAULT_MAILTO,
    delay: float = 0.3,
) -> CrossRefMatch:
    """Try multiple CrossRef search strategies to find a DOI for a reference.

    Strategies (tried in order, best overall match wins):
      1. Bibliographic query: author + title + year
      2. Title-only query
      3. Author + container-title (journal)
      4. Broad bibliographic: author surname + year
    """
    owns_client = client is None
    if owns_client:
        client = httpx.Client(headers={"User-Agent": f"citation-sentinel/0.1 (mailto:{mailto})"})

    try:
        return _discover_doi_inner(ref, client, delay)
    finally:
        if owns_client:
            client.close()


def _discover_doi_inner(
    ref: Reference,
    client: httpx.Client,
    delay: float,
) -> CrossRefMatch:
    title = ref.title or ""
    authors = ref.authors or ""
    year = ref.year or ""
    journal = ref.journal or ""
    surname = first_author_surname(authors)

    strategies: list[dict] = []

    # Strategy 1: bibliographic with author + title + year
    if title and title != "N/A":
        parts = []
        if surname:
            parts.append(surname)
        parts.append(title[:100])
        if year:
            parts.append(str(year))
        strategies.append({
            "name": "author+title+year",
            "params": {"query.bibliographic": " ".join(parts)},
        })

    # Strategy 2: title only
    if title and title != "N/A":
        strategies.append({
            "name": "title-only",
            "params": {"query.title": title[:150]},
        })

    # Strategy 3: author + journal
    if surname and journal:
        strategies.append({
            "name": "author+journal",
            "params": {
                "query.author": surname,
                "query.container-title": journal[:80],
            },
        })

    # Strategy 4: broad — surname + year + journal hint
    if surname and year:
        broad = f"{surname} {year}"
        if journal:
            broad += f" {journal[:40]}"
        strategies.append({
            "name": "author+year-broad",
            "params": {"query.bibliographic": broad},
        })

    best_score = 0.0
    best_details: dict = {}
    best_strategy: str | None = None

    for strat in strategies:
        items = _query_crossref(client, strat["params"])
        time.sleep(delay)

        for item in items:
            score, details = _score_match(ref, item, surname)
            if score > best_score:
                best_score = score
                best_details = details
                best_strategy = strat["name"]

    if not best_details:
        return CrossRefMatch()

    quality = "none"
    if best_score >= 0.6:
        quality = "good"
    elif best_score >= 0.35:
        quality = "partial"
    elif best_score > 0:
        quality = "poor"

    return CrossRefMatch(
        found=True,
        doi=best_details["doi"] if quality in ("good", "partial") else None,
        title=best_details.get("title"),
        authors=best_details.get("authors"),
        year=best_details.get("year"),
        score=round(best_score, 3),
        quality=quality,
        strategy=best_strategy,
        container=best_details.get("container"),
        work_type=best_details.get("type"),
    )


def discover_batch(
    refs: list[Reference],
    *,
    mailto: str = _DEFAULT_MAILTO,
    delay: float = 0.3,
    progress_fn=None,
) -> dict[str, CrossRefMatch]:
    """Discover DOIs for a batch of references.

    Returns a dict mapping ref.key -> CrossRefMatch.
    Only queries references that don't already have a DOI.
    """
    results: dict[str, CrossRefMatch] = {}
    to_query = [r for r in refs if not r.doi]

    with httpx.Client(
        headers={"User-Agent": f"citation-sentinel/0.1 (mailto:{mailto})"},
    ) as client:
        for i, ref in enumerate(to_query):
            match = _discover_doi_inner(ref, client, delay)
            results[ref.key] = match

            if match.doi and match.quality in ("good", "partial"):
                ref.doi = match.doi

            if progress_fn:
                progress_fn(i + 1, len(to_query), ref.key, match)

    return results


# ── Open Library fallback for books ───────────────────────────────────

@dataclass
class OpenLibraryMatch:
    found: bool = False
    title: str | None = None
    authors: str | None = None
    key: str | None = None
    year: str | None = None


def search_openlibrary(
    ref: Reference,
    *,
    client: httpx.Client | None = None,
) -> OpenLibraryMatch:
    """Search Open Library for a book reference."""
    title = ref.title or ""
    surname = first_author_surname(ref.authors)

    if not title or title == "N/A":
        return OpenLibraryMatch()

    params: dict[str, str] = {"title": title[:100], "limit": "3"}
    if surname:
        params["author"] = surname

    owns_client = client is None
    if owns_client:
        client = httpx.Client()

    try:
        resp = client.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        docs = resp.json().get("docs", [])

        for doc in docs:
            ol_title = doc.get("title", "")
            sim = _title_similarity(title, ol_title)
            ol_authors = ", ".join(doc.get("author_name", [])[:3])
            if surname and surname.lower() in ol_authors.lower():
                sim += 0.15
            if sim >= 0.4:
                return OpenLibraryMatch(
                    found=True,
                    title=ol_title,
                    authors=ol_authors,
                    key=doc.get("key", ""),
                    year=str(doc.get("first_publish_year", "")),
                )
        return OpenLibraryMatch()
    except (httpx.HTTPError, ValueError, KeyError):
        return OpenLibraryMatch()
    finally:
        if owns_client:
            client.close()
