"""
Citation role classification and falsifiability verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CitationRole(str, Enum):
    FOUNDATIONAL = "foundational"
    DATA_SOURCE = "data_source"
    METHODOLOGICAL = "methodological"
    CONTEXTUAL = "contextual"
    NARRATIVE = "narrative"
    SECONDARY = "secondary"


class Verdict(str, Enum):
    VERIFIED = "verified"
    LIKELY_REAL = "likely_real"
    UNVERIFIED = "unverified"
    SUSPICIOUS = "suspicious"


@dataclass
class Classification:
    role: CitationRole
    verdict: Verdict
    confidence: str  # high | medium | low
    evidence: str
    doi: str | None = None


# ── Context extraction ────────────────────────────────────────────────

def extract_citation_context(
    paper_path: Path,
    author_surname: str,
    year: str | None = None,
    window: int = 300,
) -> list[str]:
    """Find where a citation is used in a paper and extract surrounding context."""
    if not paper_path.exists():
        return []

    text = paper_path.read_text(encoding="utf-8", errors="replace")
    contexts: list[str] = []

    # Pattern: surname (year) or surname et al. (year)
    patterns = []
    if author_surname:
        esc = re.escape(author_surname)
        patterns.append(re.compile(rf"{esc}.*?\({year}\)" if year else esc, re.IGNORECASE))
        if year:
            patterns.append(re.compile(rf"\({year}\).*?{esc}", re.IGNORECASE))

    for pat in patterns:
        for m in pat.finditer(text):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            # Clean up
            snippet = re.sub(r"\s+", " ", snippet)
            if snippet not in contexts:
                contexts.append(snippet)

    return contexts[:3]


# ── Role classification ───────────────────────────────────────────────

_FOUNDATIONAL_SIGNALS = [
    r"foundational", r"fundamental", r"seminal", r"proved that",
    r"established", r"theorem", r"first showed", r"introduced by",
    r"defined by", r"axiom", r"postulate",
]

_DATA_SIGNALS = [
    r"measured", r"reported", r"experimental", r"data from",
    r"values from", r"according to.*data", r"observations",
    r"CODATA", r"NIST", r"evaluated",
]

_METHOD_SIGNALS = [
    r"method", r"algorithm", r"technique", r"approach",
    r"framework", r"model", r"procedure", r"protocol",
    r"following.*approach", r"using the method",
]


def classify_role(
    contexts: list[str],
    title: str | None = None,
) -> CitationRole:
    """Classify a citation's role based on its usage context."""
    combined = " ".join(contexts).lower()
    if title:
        combined += " " + title.lower()

    for pattern in _FOUNDATIONAL_SIGNALS:
        if re.search(pattern, combined):
            return CitationRole.FOUNDATIONAL

    for pattern in _DATA_SIGNALS:
        if re.search(pattern, combined):
            return CitationRole.DATA_SOURCE

    for pattern in _METHOD_SIGNALS:
        if re.search(pattern, combined):
            return CitationRole.METHODOLOGICAL

    return CitationRole.CONTEXTUAL


# ── Falsifiability verdict ────────────────────────────────────────────

def determine_verdict(
    *,
    crossref_found: bool = False,
    crossref_quality: str = "none",
    crossref_doi: str | None = None,
    doi_validated: bool = False,
    openlibrary_found: bool = False,
) -> Classification:
    """Determine the falsifiability verdict for a reference."""

    if doi_validated or (crossref_found and crossref_quality == "good" and crossref_doi):
        return Classification(
            role=CitationRole.CONTEXTUAL,  # overridden later
            verdict=Verdict.VERIFIED,
            confidence="high",
            evidence=f"CrossRef {crossref_quality} match, DOI: {crossref_doi}",
            doi=crossref_doi,
        )

    if crossref_found and crossref_quality in ("good", "partial"):
        return Classification(
            role=CitationRole.CONTEXTUAL,
            verdict=Verdict.VERIFIED,
            confidence="high" if crossref_quality == "good" else "medium",
            evidence=f"CrossRef {crossref_quality} match (score-based)",
            doi=crossref_doi,
        )

    if openlibrary_found:
        return Classification(
            role=CitationRole.CONTEXTUAL,
            verdict=Verdict.LIKELY_REAL,
            confidence="medium",
            evidence="Found in Open Library catalogue",
        )

    if crossref_found and crossref_quality == "poor":
        return Classification(
            role=CitationRole.CONTEXTUAL,
            verdict=Verdict.LIKELY_REAL,
            confidence="low",
            evidence="CrossRef poor match — may exist under variant metadata",
        )

    return Classification(
        role=CitationRole.CONTEXTUAL,
        verdict=Verdict.UNVERIFIED,
        confidence="low",
        evidence="Not found in CrossRef or Open Library",
    )
