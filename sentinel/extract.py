"""
Reference extraction from Markdown, LaTeX, and BibTeX files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Reference:
    """A single parsed reference entry."""

    raw: str
    authors: str | None = None
    year: str | None = None
    title: str | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    source_file: str | None = None
    source_paper: str | None = None
    key: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            self.key = canonical_key(self.authors, self.year)


# ── Regex patterns ────────────────────────────────────────────────────

# Headings that start a references section
_REF_HEADING = re.compile(
    r"^(#{1,4})\s+"
    r"(?:references?|reference\s+paper\s+citations?|"
    r"external\s+references?|bibliography)"
    r"(?:\s*\{-\})?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_DOI = re.compile(r"10\.\d{4,9}/[^\s)>\]]+")
_URL = re.compile(r"https?://[^\s)>\]]+")
_YEAR_PAREN = re.compile(r"\((1[6-9]\d{2}|20[0-2]\d)[a-z]?\)")
_AUTHOR_YEAR = re.compile(r"^(.+?)\s*\(((?:1[6-9]\d{2}|20[0-2]\d)[a-z]?)\)")
_NUMBERED_PREFIX = re.compile(r"^\[\d+\]\s*")

# BibTeX
_BIB_ENTRY = re.compile(
    r"@(\w+)\s*\{\s*([^,]*),\s*((?:[^@](?!@\w+\s*\{))*)",
    re.DOTALL,
)
_BIB_FIELD = re.compile(r"(\w+)\s*=\s*[{\"]((?:[^{}]|\{[^}]*\})*)[}\"]")

# LaTeX \bibliography / \addbibresource
_LATEX_BIBFILE = re.compile(r"\\(?:bibliography|addbibresource)\{([^}]+)\}")


# ── Canonical key ─────────────────────────────────────────────────────

def canonical_key(authors: str | None, year: str | None) -> str:
    """Generate a dedup key: first_author_surname_year."""
    if not authors:
        return f"unknown_{year or 'unknown'}"
    first = authors.split(",")[0].split("&")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else "unknown"
    surname = re.sub(r"[^a-zA-Z]", "", surname).lower()
    return f"{surname}_{year or 'unknown'}"


def first_author_surname(authors: str | None) -> str:
    """Extract the last name of the first author."""
    if not authors:
        return ""
    s = re.sub(r"\bet\s+al\.?\b", "", authors).strip()
    s = re.split(r"[,&]|\band\b", s)[0].strip()
    if "," in s:
        return s.split(",")[0].strip()
    parts = s.split()
    return parts[-1].strip().rstrip(".") if parts else s


# ── Markdown extraction ───────────────────────────────────────────────

def _next_heading_re(level: int) -> re.Pattern:
    return re.compile(r"^(#{1," + str(level) + r"})\s+\S", re.MULTILINE)


def _extract_ref_section(text: str) -> str | None:
    """Return raw text of the references section in a Markdown file."""
    m = _REF_HEADING.search(text)
    if not m:
        return None
    level = len(m.group(1))
    rest = text[m.end():]
    end = _next_heading_re(level).search(rest)
    return rest[: end.start()].strip() if end else rest.strip()


def _split_md_entries(ref_text: str) -> list[str]:
    """Split a Markdown references section into individual entries."""
    lines = ref_text.split("\n")
    entries: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip subheadings
        if re.match(r"^#{1,4}\s+", stripped):
            if current:
                entries.append(" ".join(current))
                current = []
            continue

        # Skip bold section headers
        if re.match(r"^\*\*[^*]+\*\*\s*$", stripped):
            if current:
                entries.append(" ".join(current))
                current = []
            continue

        # Skip table headers/separators
        if re.match(r"^\|.*\|$", stripped) and ("Ref" in stripped or "---" in stripped):
            continue

        # Table data row
        if re.match(r"^\|.*\|$", stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells:
                entries.append(" ".join(cells))
                current = []
            continue

        # Bullet or numbered entry
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            if current:
                entries.append(" ".join(current))
            current = [re.sub(r"^[-*]\s+|^\d+\.\s+", "", stripped)]
        elif stripped == "":
            if current:
                entries.append(" ".join(current))
                current = []
        elif current:
            current.append(stripped)
        elif stripped:
            current = [stripped]

    if current:
        entries.append(" ".join(current))

    # Filter junk
    result = []
    for e in entries:
        e = e.strip()
        if len(e) < 20:
            continue
        if re.match(r"^\*\*[^*]+\*\*\s*$", e):
            continue
        if re.match(r"^\*\*(External|Internal|This Research|Link \d)\b", e):
            continue
        result.append(e)
    return result


def _parse_md_entry(raw: str) -> Reference:
    """Parse a single Markdown reference string into structured fields."""
    cleaned = _NUMBERED_PREFIX.sub("", raw).strip()

    doi = None
    doi_m = _DOI.search(raw)
    if doi_m:
        doi = doi_m.group(0).rstrip(".")

    url = None
    url_m = _URL.search(raw)
    if url_m:
        url = url_m.group(0).rstrip(".)")

    authors = None
    year = None
    ay = _AUTHOR_YEAR.match(cleaned)
    if ay:
        authors = ay.group(1).strip().rstrip(",")
        year = ay.group(2)
    else:
        ym = _YEAR_PAREN.search(cleaned)
        if ym:
            year = ym.group(1)

    title = None
    title_m = re.search(
        r"\((?:1[6-9]\d{2}|20[0-2]\d)[a-z]?\)[.\s]+(.+?)(?:\*|$)", cleaned
    )
    if title_m:
        t = title_m.group(1).strip().strip('"').strip("*").strip(".")
        if len(t) > 10:
            title = t

    journal = None
    journal_m = re.search(r"\*([^*]+)\*", cleaned)
    if journal_m:
        journal = journal_m.group(1).strip()

    return Reference(
        raw=raw,
        authors=authors,
        year=year,
        title=title,
        journal=journal,
        doi=doi,
        url=url,
    )


def extract_markdown(path: Path) -> list[Reference]:
    """Extract all references from a Markdown file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    section = _extract_ref_section(text)
    if not section:
        return []
    raw_entries = _split_md_entries(section)
    refs = []
    for raw in raw_entries:
        ref = _parse_md_entry(raw)
        ref.source_file = str(path)
        ref.source_paper = path.stem
        refs.append(ref)
    return refs


# ── BibTeX extraction ─────────────────────────────────────────────────

def extract_bibtex(path: Path) -> list[Reference]:
    """Extract references from a .bib file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = []

    for match in _BIB_ENTRY.finditer(text):
        entry_type = match.group(1).lower()
        cite_key = match.group(2).strip()
        body = match.group(3)

        if entry_type in ("comment", "string", "preamble"):
            continue

        fields: dict[str, str] = {}
        for fm in _BIB_FIELD.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2).strip()

        authors = fields.get("author")
        year = fields.get("year")
        title = fields.get("title", "").strip("{}")
        journal = fields.get("journal") or fields.get("booktitle")
        doi = fields.get("doi")
        url = fields.get("url")

        raw = f"{authors or '?'} ({year or '?'}). {title}."
        if journal:
            raw += f" {journal}."

        ref = Reference(
            raw=raw,
            authors=authors,
            year=year,
            title=title if len(title) > 5 else None,
            journal=journal,
            doi=doi,
            url=url,
            source_file=str(path),
            source_paper=cite_key,
            key=cite_key if cite_key else canonical_key(authors, year),
        )
        refs.append(ref)
    return refs


# ── LaTeX extraction ──────────────────────────────────────────────────

def extract_latex(path: Path) -> list[Reference]:
    """Extract references from a LaTeX file.

    If the file contains \\bibliography{...} or \\addbibresource{...},
    attempt to find and parse the referenced .bib file.
    Falls back to parsing \\bibitem entries if present.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    refs: list[Reference] = []

    # Try to find associated .bib file
    bib_match = _LATEX_BIBFILE.search(text)
    if bib_match:
        for bib_name in bib_match.group(1).split(","):
            bib_name = bib_name.strip()
            if not bib_name.endswith(".bib"):
                bib_name += ".bib"
            bib_path = path.parent / bib_name
            if bib_path.exists():
                refs.extend(extract_bibtex(bib_path))

    # Also try \bibitem entries (thebibliography environment)
    for m in re.finditer(r"\\bibitem(?:\[.*?\])?\{([^}]+)\}\s*(.*?)(?=\\bibitem|\\end\{thebibliography\}|$)", text, re.DOTALL):
        cite_key = m.group(1)
        body = m.group(2).strip()
        # Clean LaTeX commands
        body = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", body)
        body = re.sub(r"[{}~]", " ", body)
        body = re.sub(r"\s+", " ", body).strip()

        if len(body) < 20:
            continue

        ref = _parse_md_entry(body)  # reuse markdown parser for the text
        ref.source_file = str(path)
        ref.source_paper = cite_key
        ref.key = cite_key
        refs.append(ref)

    return refs


# ── Unified extraction ────────────────────────────────────────────────

# Common paper filename patterns
PAPER_GLOBS = [
    "PAPER__*.md",
    "paper.md",
    "R-*.md",
    "*.md",
    "*.tex",
    "*.bib",
]


def find_papers(root: Path, globs: list[str] | None = None) -> list[Path]:
    """Discover paper files under a directory tree."""
    if globs is None:
        globs = PAPER_GLOBS
    seen: set[Path] = set()
    papers: list[Path] = []
    for g in globs:
        for p in sorted(root.rglob(g)):
            if p in seen:
                continue
            # Skip common non-paper files
            if p.name.lower() in ("readme.md", "changelog.md", "contributing.md", "license.md"):
                continue
            seen.add(p)
            papers.append(p)
    return papers


def extract_file(path: Path) -> list[Reference]:
    """Extract references from a single file, auto-detecting format."""
    suffix = path.suffix.lower()
    if suffix == ".bib":
        return extract_bibtex(path)
    if suffix == ".tex":
        return extract_latex(path)
    # Default: Markdown
    return extract_markdown(path)


def extract_all(root: Path, globs: list[str] | None = None) -> list[Reference]:
    """Extract references from all papers under a directory."""
    papers = find_papers(root, globs)
    all_refs: list[Reference] = []
    for paper in papers:
        all_refs.extend(extract_file(paper))
    return all_refs
