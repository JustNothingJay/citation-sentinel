"""Tests for CrossRef discovery and DOI lookup."""

import pytest

from sentinel.discover import (
    CrossRefMatch,
    _title_similarity,
)
from sentinel.extract import Reference


class TestTitleSimilarity:
    """Test the word-overlap title similarity function."""

    def test_identical(self):
        score = _title_similarity(
            "A Mathematical Theory of Communication",
            "A Mathematical Theory of Communication",
        )
        assert score == pytest.approx(1.0)

    def test_subset(self):
        score = _title_similarity(
            "Mathematical Theory Communication",
            "A Mathematical Theory of Communication",
        )
        # All query words found in target
        assert score > 0.8

    def test_no_overlap(self):
        score = _title_similarity(
            "Quantum Electrodynamics",
            "Agricultural Economics in the 21st Century",
        )
        assert score < 0.2

    def test_partial_overlap(self):
        score = _title_similarity(
            "Theory of Relativity",
            "General Theory of Gravity and Relativity",
        )
        assert 0.3 < score < 0.9

    def test_empty_strings(self):
        assert _title_similarity("", "Something") == 0.0
        assert _title_similarity("Something", "") == 0.0
        assert _title_similarity("", "") == 0.0


class TestCrossRefMatch:
    """Test CrossRefMatch dataclass defaults."""

    def test_defaults(self):
        m = CrossRefMatch()
        assert m.found is False
        assert m.doi is None
        assert m.quality == "none"
        assert m.score == 0.0
