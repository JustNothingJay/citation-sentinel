"""
Inventory: the central data structure that holds the full audit state.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .extract import Reference


@dataclass
class InventoryEntry:
    """One reference in the inventory, with all audit results."""

    key: str
    authors: str | None = None
    year: str | None = None
    title: str | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    cited_by: list[str] = field(default_factory=list)
    raw_forms: list[dict] = field(default_factory=list)

    # Populated by discover
    crossref_quality: str | None = None
    crossref_score: float | None = None
    crossref_strategy: str | None = None
    crossref_doi: str | None = None
    crossref_title: str | None = None

    # Populated by validate
    validation_status: str | None = None
    validation_http_code: int | None = None

    # Populated by deep-verify / classify
    openlibrary_found: bool = False
    verdict: str | None = None
    verdict_confidence: str | None = None
    verdict_evidence: str | None = None
    role: str | None = None
    contexts: list[str] = field(default_factory=list)


@dataclass
class Inventory:
    """The complete citation inventory for a research corpus."""

    generated: str = ""
    tool_version: str = "0.1.0"
    papers_scanned: int = 0
    entries: dict[str, InventoryEntry] = field(default_factory=dict)
    paper_refs: dict[str, list[str]] = field(default_factory=dict)

    # Summary stats (populated after stages complete)
    lookup_attempted: int = 0
    lookup_found: int = 0
    lookup_poor: int = 0
    validated_count: int = 0
    validated_passed: int = 0
    validated_failed: int = 0
    validated_paywall: int = 0

    def add_reference(self, ref: Reference, paper_name: str) -> None:
        """Add a reference to the inventory, merging if it already exists."""
        key = ref.key
        if key in self.entries:
            entry = self.entries[key]
            if paper_name not in entry.cited_by:
                entry.cited_by.append(paper_name)
            # Fill missing fields
            for attr in ("doi", "url", "title", "journal"):
                if not getattr(entry, attr) and getattr(ref, attr):
                    setattr(entry, attr, getattr(ref, attr))
            entry.raw_forms.append({"source": paper_name, "raw": ref.raw[:300]})
        else:
            self.entries[key] = InventoryEntry(
                key=key,
                authors=ref.authors,
                year=ref.year,
                title=ref.title,
                journal=ref.journal,
                doi=ref.doi,
                url=ref.url,
                cited_by=[paper_name],
                raw_forms=[{"source": paper_name, "raw": ref.raw[:300]}],
            )

        # Track which papers cite which keys
        if paper_name not in self.paper_refs:
            self.paper_refs[paper_name] = []
        if key not in self.paper_refs[paper_name]:
            self.paper_refs[paper_name].append(key)

    def save(self, path: Path) -> None:
        """Save inventory to JSON."""
        data = {
            "generated": self.generated or time.strftime("%Y-%m-%d %H:%M:%S"),
            "tool_version": self.tool_version,
            "papers_scanned": self.papers_scanned,
            "summary": {
                "total_entries": len(self.entries),
                "lookup": {
                    "attempted": self.lookup_attempted,
                    "found": self.lookup_found,
                    "poor": self.lookup_poor,
                },
                "validation": {
                    "checked": self.validated_count,
                    "passed": self.validated_passed,
                    "failed": self.validated_failed,
                    "paywall": self.validated_paywall,
                },
            },
            "entries": {k: asdict(v) for k, v in self.entries.items()},
            "paper_refs": self.paper_refs,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Inventory":
        """Load inventory from JSON."""
        data = json.loads(path.read_text(encoding="utf-8"))
        inv = cls(
            generated=data.get("generated", ""),
            tool_version=data.get("tool_version", "0.1.0"),
            papers_scanned=data.get("papers_scanned", 0),
        )
        summary = data.get("summary", {})
        lu = summary.get("lookup", {})
        inv.lookup_attempted = lu.get("attempted", 0)
        inv.lookup_found = lu.get("found", 0)
        inv.lookup_poor = lu.get("poor", 0)
        va = summary.get("validation", {})
        inv.validated_count = va.get("checked", 0)
        inv.validated_passed = va.get("passed", 0)
        inv.validated_failed = va.get("failed", 0)
        inv.validated_paywall = va.get("paywall", 0)

        for key, edata in data.get("entries", {}).items():
            inv.entries[key] = InventoryEntry(**{
                k: v for k, v in edata.items()
                if k in InventoryEntry.__dataclass_fields__
            })
        inv.paper_refs = data.get("paper_refs", {})
        return inv
