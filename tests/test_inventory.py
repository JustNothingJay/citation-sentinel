"""Tests for inventory data structure and serialization."""

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from sentinel.inventory import Inventory, InventoryEntry
from sentinel.extract import Reference


class TestInventoryEntry:
    """Test inventory entry dataclass."""

    def test_asdict(self):
        entry = InventoryEntry(
            key="einstein_1905",
            authors="Einstein, A.",
            year="1905",
            title="On the Electrodynamics of Moving Bodies",
            doi="10.1002/andp.19053220607",
        )
        d = asdict(entry)
        assert d["key"] == "einstein_1905"
        assert d["doi"] == "10.1002/andp.19053220607"

    def test_entry_defaults(self):
        entry = InventoryEntry(key="test")
        assert entry.authors is None
        assert entry.cited_by == []
        assert entry.crossref_quality is None
        assert entry.openlibrary_found is False


class TestInventory:
    """Test inventory management."""

    def test_add_reference(self):
        inv = Inventory(generated="2026-01-01", papers_scanned=1)
        ref = Reference(
            raw="Einstein, A. (1905). Title.",
            authors="Einstein, A.",
            year="1905",
            title="On the Electrodynamics",
            key="einstein_1905",
        )
        inv.add_reference(ref, "paper-01")
        assert len(inv.entries) == 1
        assert "einstein_1905" in inv.entries

    def test_merge_duplicate(self):
        inv = Inventory(generated="2026-01-01", papers_scanned=2)
        ref = Reference(
            raw="Einstein, A. (1905). Title.",
            authors="Einstein, A.",
            year="1905",
            title="On the Electrodynamics",
            key="einstein_1905",
        )
        inv.add_reference(ref, "paper-01")
        inv.add_reference(ref, "paper-02")
        assert len(inv.entries) == 1
        entry = inv.entries["einstein_1905"]
        assert "paper-01" in entry.cited_by
        assert "paper-02" in entry.cited_by

    def test_save_load_roundtrip(self):
        inv = Inventory(generated="2026-01-01", papers_scanned=1)
        ref = Reference(
            raw="Test reference",
            authors="Smith, J.",
            year="2024",
            title="A Test",
            key="smith_2024_test",
        )
        inv.add_reference(ref, "paper-01")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = Path(f.name)

        try:
            inv.save(path)
            loaded = Inventory.load(path)
            assert len(loaded.entries) == 1
            assert "smith_2024_test" in loaded.entries
            assert loaded.papers_scanned == 1
        finally:
            path.unlink()
