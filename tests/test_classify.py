"""Tests for citation classification and verdicts."""

import pytest

from sentinel.classify import (
    CitationRole,
    Verdict,
    Classification,
    classify_role,
    determine_verdict,
)


class TestClassifyRole:
    """Test citation role classification."""

    def test_foundational_keywords(self):
        contexts = [
            "Building on the foundational work of Einstein (1905), we derive..."
        ]
        role = classify_role(contexts, "On the Electrodynamics of Moving Bodies")
        assert role == CitationRole.FOUNDATIONAL

    def test_data_source(self):
        contexts = [
            "Using data from the dataset provided by NIST CODATA (2018)..."
        ]
        role = classify_role(contexts, "CODATA recommended values of physical constants")
        assert role in (CitationRole.DATA_SOURCE, CitationRole.CONTEXTUAL)

    def test_methodological(self):
        contexts = [
            "Following the method described in Smith (2020), we applied..."
        ]
        role = classify_role(contexts, "A Novel Method for Analysis")
        assert role == CitationRole.METHODOLOGICAL

    def test_no_context_defaults_contextual(self):
        role = classify_role([], "Some Paper Title")
        assert role == CitationRole.CONTEXTUAL


class TestDetermineVerdict:
    """Test falsifiability verdict logic."""

    def test_verified_good_crossref(self):
        c = determine_verdict(
            crossref_found=True,
            crossref_quality="good",
            crossref_doi="10.1234/test",
            openlibrary_found=True,
        )
        assert c.verdict == Verdict.VERIFIED

    def test_likely_real_partial(self):
        c = determine_verdict(
            crossref_found=True,
            crossref_quality="partial",
            crossref_doi="10.1234/test",
            openlibrary_found=False,
        )
        assert c.verdict in (Verdict.VERIFIED, Verdict.LIKELY_REAL)

    def test_unverified_no_matches(self):
        c = determine_verdict(
            crossref_found=False,
            crossref_quality="none",
            crossref_doi=None,
            openlibrary_found=False,
        )
        assert c.verdict in (Verdict.UNVERIFIED, Verdict.SUSPICIOUS)

    def test_likely_real_openlibrary_only(self):
        c = determine_verdict(
            crossref_found=False,
            crossref_quality="none",
            crossref_doi=None,
            openlibrary_found=True,
        )
        assert c.verdict == Verdict.LIKELY_REAL
