"""Tests for reference extraction from Markdown, BibTeX, and LaTeX."""

from pathlib import Path

import pytest

from sentinel.extract import (
    Reference,
    extract_file,
    extract_markdown,
    extract_bibtex,
    canonical_key,
    first_author_surname,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestMarkdownExtraction:
    """Tests for Markdown reference parsing."""

    def test_extract_numbered_references(self):
        refs = extract_file(FIXTURES / "sample_paper.md")
        # Should find numbered entries + table entry
        assert len(refs) >= 5

    def test_finds_doi_in_reference(self):
        refs = extract_file(FIXTURES / "sample_paper.md")
        dois = [r.doi for r in refs if r.doi]
        assert "10.1002/andp.19053220607" in dois
        assert "10.1002/andp.19013090310" in dois

    def test_extracts_authors(self):
        refs = extract_file(FIXTURES / "sample_paper.md")
        authors = [r.authors for r in refs if r.authors]
        # At least some references should have parsed authors
        assert any("Einstein" in a for a in authors)

    def test_extracts_year(self):
        refs = extract_file(FIXTURES / "sample_paper.md")
        years = [r.year for r in refs if r.year]
        assert "1905" in years
        assert "1948" in years

    def test_extracts_table_entries(self):
        refs = extract_file(FIXTURES / "sample_paper.md")
        # Should extract Noether from the table
        all_text = " ".join(r.raw for r in refs)
        assert "Noether" in all_text

    def test_inline_markdown_string(self, tmp_path):
        text = """## Bibliography

- Turing, A. M. (1936). On Computable Numbers, with an Application to the Entscheidungsproblem. *Proceedings of the London Mathematical Society*, 42(1), 230–265.
- Gödel, K. (1931). Über formal unentscheidbare Sätze. *Monatshefte für Mathematik und Physik*, 38, 173–198.
"""
        p = tmp_path / "test.md"
        p.write_text(text, encoding="utf-8")
        refs = extract_markdown(p)
        assert len(refs) == 2
        assert any("Turing" in (r.authors or "") for r in refs)
        assert any("Gödel" in (r.authors or r.raw) for r in refs)


class TestBibTeXExtraction:
    """Tests for BibTeX reference parsing."""

    def test_extract_bibtex_file(self):
        refs = extract_file(FIXTURES / "sample_refs.bib")
        assert len(refs) == 3

    def test_bibtex_keys(self):
        refs = extract_file(FIXTURES / "sample_refs.bib")
        keys = {r.key for r in refs}
        assert "einstein1905" in keys
        assert "feynman1985" in keys
        assert "shannon1948" in keys

    def test_bibtex_doi_extraction(self):
        refs = extract_file(FIXTURES / "sample_refs.bib")
        einstein = next(r for r in refs if r.key == "einstein1905")
        assert einstein.doi == "10.1002/andp.19053220607"

    def test_bibtex_field_parsing(self):
        refs = extract_file(FIXTURES / "sample_refs.bib")
        shannon = next(r for r in refs if r.key == "shannon1948")
        assert "Shannon" in (shannon.authors or "")
        assert shannon.year == "1948"
        assert "Mathematical Theory" in (shannon.title or "")

    def test_bibtex_inline_string(self, tmp_path):
        bib = """@inproceedings{test2024,
  author = {Smith, John and Doe, Jane},
  title  = {A Test Paper},
  year   = {2024},
  booktitle = {Test Conference}
}"""
        p = tmp_path / "test.bib"
        p.write_text(bib, encoding="utf-8")
        refs = extract_bibtex(p)
        assert len(refs) == 1
        assert refs[0].key == "test2024"
        assert refs[0].year == "2024"


class TestCanonicalKey:
    """Tests for reference key generation."""

    def test_basic_key(self):
        key = canonical_key("Einstein, A.", "1905")
        assert key == "einstein_1905"

    def test_no_author(self):
        key = canonical_key("", "2020")
        assert key == "unknown_2020"

    def test_no_year(self):
        key = canonical_key("Smith, J.", "")
        assert key == "smith_unknown"

    def test_none_author(self):
        key = canonical_key(None, "2020")
        assert key == "unknown_2020"


class TestFirstAuthorSurname:
    """Tests for author surname extraction."""

    def test_comma_format(self):
        assert first_author_surname("Einstein, A.") == "Einstein"

    def test_and_separator(self):
        assert first_author_surname("Smith, J. and Doe, A.") == "Smith"

    def test_ampersand_separator(self):
        assert first_author_surname("Smith, J. & Doe, A.") == "Smith"

    def test_initials_first(self):
        assert first_author_surname("A. Einstein") == "Einstein"

    def test_empty(self):
        assert first_author_surname("") == ""
        assert first_author_surname(None) == ""
