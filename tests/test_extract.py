"""Tests for reference extraction from Markdown, BibTeX, LaTeX, RIS, EndNote XML, and CSL-JSON."""

from pathlib import Path

import pytest

from sentinel.extract import (
    Reference,
    extract_file,
    extract_markdown,
    extract_bibtex,
    extract_ris,
    extract_endnote_xml,
    extract_csl_json,
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


class TestFootnoteExtraction:
    """Tests for Markdown footnote-style reference parsing."""

    def test_footnote_references(self, tmp_path):
        text = """# My Paper

Some text with a citation[^1] and another[^2].

## References

[^1]: Einstein, A. (1905). On the Electrodynamics of Moving Bodies. *Annalen der Physik*. DOI: 10.1002/andp.19053220607
[^2]: Shannon, C. E. (1948). A Mathematical Theory of Communication. *Bell System Technical Journal*.
"""
        p = tmp_path / "footnotes.md"
        p.write_text(text, encoding="utf-8")
        refs = extract_markdown(p)
        assert len(refs) >= 2
        assert any("Einstein" in (r.authors or r.raw) for r in refs)
        assert any("Shannon" in (r.authors or r.raw) for r in refs)

    def test_footnote_outside_ref_section(self, tmp_path):
        text = """# My Paper

Some body text.

[^1]: Feynman, R. P. (1985). QED: The Strange Theory of Light and Matter.
"""
        p = tmp_path / "footnotes_only.md"
        p.write_text(text, encoding="utf-8")
        refs = extract_markdown(p)
        assert len(refs) >= 1
        assert any("Feynman" in (r.authors or r.raw) for r in refs)


class TestRISExtraction:
    """Tests for RIS format parsing."""

    def test_extract_ris_file(self):
        refs = extract_ris(FIXTURES / "sample_refs.ris")
        assert len(refs) == 2

    def test_ris_authors(self):
        refs = extract_ris(FIXTURES / "sample_refs.ris")
        shannon = next(r for r in refs if "Shannon" in (r.authors or ""))
        assert "Weaver" in shannon.authors

    def test_ris_doi(self):
        refs = extract_ris(FIXTURES / "sample_refs.ris")
        shannon = next(r for r in refs if "Shannon" in (r.authors or ""))
        assert shannon.doi == "10.1002/j.1538-7305.1948.tb01338.x"

    def test_ris_year(self):
        refs = extract_ris(FIXTURES / "sample_refs.ris")
        feynman = next(r for r in refs if "Feynman" in (r.authors or ""))
        assert feynman.year == "1985"

    def test_ris_url(self):
        refs = extract_ris(FIXTURES / "sample_refs.ris")
        feynman = next(r for r in refs if "Feynman" in (r.authors or ""))
        assert feynman.url is not None

    def test_ris_via_extract_file(self):
        refs = extract_file(FIXTURES / "sample_refs.ris")
        assert len(refs) == 2


class TestEndNoteXMLExtraction:
    """Tests for EndNote XML format parsing."""

    def test_extract_endnote_xml(self):
        refs = extract_endnote_xml(FIXTURES / "sample_refs.xml")
        assert len(refs) == 2

    def test_endnote_authors(self):
        refs = extract_endnote_xml(FIXTURES / "sample_refs.xml")
        einstein = next(r for r in refs if "Einstein" in (r.authors or ""))
        assert "Albert" in einstein.authors

    def test_endnote_doi(self):
        refs = extract_endnote_xml(FIXTURES / "sample_refs.xml")
        einstein = next(r for r in refs if "Einstein" in (r.authors or ""))
        assert einstein.doi == "10.1002/andp.19053220607"

    def test_endnote_year(self):
        refs = extract_endnote_xml(FIXTURES / "sample_refs.xml")
        turing = next(r for r in refs if "Turing" in (r.authors or ""))
        assert turing.year == "1936"

    def test_endnote_journal(self):
        refs = extract_endnote_xml(FIXTURES / "sample_refs.xml")
        einstein = next(r for r in refs if "Einstein" in (r.authors or ""))
        assert "Annalen" in (einstein.journal or "")

    def test_endnote_via_extract_file(self):
        refs = extract_file(FIXTURES / "sample_refs.xml")
        assert len(refs) == 2


class TestCSLJSONExtraction:
    """Tests for CSL-JSON format parsing."""

    def test_extract_csl_json(self):
        refs = extract_csl_json(FIXTURES / "sample_refs.json")
        assert len(refs) == 2

    def test_csl_authors(self):
        refs = extract_csl_json(FIXTURES / "sample_refs.json")
        einstein = next(r for r in refs if r.key == "einstein1905")
        assert "Einstein" in (einstein.authors or "")

    def test_csl_doi(self):
        refs = extract_csl_json(FIXTURES / "sample_refs.json")
        shannon = next(r for r in refs if r.key == "shannon1948")
        assert shannon.doi == "10.1002/j.1538-7305.1948.tb01338.x"

    def test_csl_year(self):
        refs = extract_csl_json(FIXTURES / "sample_refs.json")
        einstein = next(r for r in refs if r.key == "einstein1905")
        assert einstein.year == "1905"

    def test_csl_journal(self):
        refs = extract_csl_json(FIXTURES / "sample_refs.json")
        shannon = next(r for r in refs if r.key == "shannon1948")
        assert "Bell System" in (shannon.journal or "")

    def test_csl_via_extract_file(self):
        refs = extract_file(FIXTURES / "sample_refs.json")
        assert len(refs) == 2


class TestBibTeXEdgeCases:
    """Tests for BibTeX nested braces and string concatenation."""

    def test_nested_braces_in_title(self, tmp_path):
        bib = r"""@article{test2024,
  author = {Smith, John},
  title  = {The {Schr{\"o}dinger} Equation in {3D}},
  year   = {2024},
  journal = {Physical Review}
}"""
        p = tmp_path / "nested.bib"
        p.write_text(bib, encoding="utf-8")
        refs = extract_bibtex(p)
        assert len(refs) == 1
        assert "dinger" in (refs[0].title or "")
        assert "3D" in (refs[0].title or "")

    def test_string_concatenation(self, tmp_path):
        bib = """@string{jnl_bell = "Bell System Technical Journal"}

@article{shannon1948,
  author  = {Shannon, Claude E.},
  title   = {A Mathematical Theory of Communication},
  year    = {1948},
  journal = jnl_bell
}"""
        p = tmp_path / "concat.bib"
        p.write_text(bib, encoding="utf-8")
        refs = extract_bibtex(p)
        assert len(refs) == 1
        assert "Bell" in (refs[0].journal or "")
