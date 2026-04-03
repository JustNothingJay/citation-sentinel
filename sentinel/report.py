"""
Report generation — Markdown and JSON output.
"""

from __future__ import annotations

import time
from pathlib import Path

from .inventory import Inventory


def generate_markdown(inv: Inventory) -> str:
    """Generate a human-readable Markdown audit report."""
    lines: list[str] = []

    entries = inv.entries
    total = len(entries)

    lines.extend([
        "# Citation Audit Report",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Tool: citation-sentinel v{inv.tool_version}",
        "",
        "## Summary",
        f"- Papers scanned: {inv.papers_scanned}",
        f"- Total unique citations: {total}",
    ])

    with_doi = [e for e in entries.values() if e.doi]
    without_doi = [e for e in entries.values() if not e.doi]
    lines.append(f"- With DOI: {len(with_doi)}")
    lines.append(f"- Without DOI: {len(without_doi)}")

    # Lookup summary
    if inv.lookup_attempted:
        lines.extend([
            "",
            "## CrossRef Lookup Results",
            f"- Attempted: {inv.lookup_attempted}",
            f"- DOIs found (good match): {inv.lookup_found}",
            f"- Poor matches: {inv.lookup_poor}",
        ])

    # Validation summary
    if inv.validated_count:
        lines.extend([
            "",
            "## DOI Validation Results",
            f"- Checked: {inv.validated_count}",
            f"- Passed: {inv.validated_passed}",
            f"- Failed: {inv.validated_failed}",
            f"- Paywall-confirmed: {inv.validated_paywall}",
        ])

    # Fabrication flags (poor CrossRef match)
    poor = [e for e in entries.values() if e.crossref_quality == "poor"]
    if poor:
        lines.extend(["", "## Potential Fabrication Flags (poor CrossRef match)"])
        lines.append("These references could not be closely matched to any known publication:")
        for e in poor:
            lines.append(
                f"- **{e.key}**: {e.authors or '?'} ({e.year or '?'}). "
                f"Title: {(e.title or 'N/A')[:80]}"
            )
            if e.crossref_title:
                lines.append(f"  - Best CrossRef match: \"{e.crossref_title[:80]}\"")

    # No-result entries
    no_result = [
        e for e in entries.values()
        if e.crossref_quality == "none" and not e.doi
    ]
    if no_result:
        lines.extend(["", "## Not Found in CrossRef"])
        for e in no_result:
            lines.append(
                f"- **{e.key}**: {e.authors or '?'} ({e.year or '?'}). "
                f"Title: {(e.title or 'N/A')[:80]}"
            )

    # Most-cited references
    lines.extend(["", "## Most-Cited References"])
    sorted_refs = sorted(entries.values(), key=lambda e: len(e.cited_by), reverse=True)
    for e in sorted_refs[:15]:
        doi_str = f"DOI: {e.doi}" if e.doi else "NO DOI"
        papers = ", ".join(e.cited_by[:5])
        if len(e.cited_by) > 5:
            papers += f" (+{len(e.cited_by) - 5} more)"
        lines.append(
            f"- **{e.key}** ({len(e.cited_by)} papers) — "
            f"{e.authors or '?'}, {e.year or '?'}. {doi_str}. Cited by: {papers}"
        )

    # Failed validations
    failed = [e for e in entries.values() if e.validation_status == "failed"]
    if failed:
        lines.extend(["", "## Failed Validations"])
        for e in failed:
            lines.append(
                f"- **{e.key}**: DOI {e.doi} — HTTP {e.validation_http_code}"
            )

    # Deep verification verdicts
    verified = [e for e in entries.values() if e.verdict]
    if verified:
        from collections import Counter
        vc = Counter(e.verdict for e in verified)
        rc = Counter(e.role for e in verified if e.role)

        lines.extend([
            "",
            "---",
            "",
            "## Deep Verification Results",
            f"**{len(verified)} references** deep-verified.",
            "",
            "### Verdict Summary",
            "| Verdict | Count |",
            "|---------|-------|",
        ])
        for v in ("verified", "likely_real", "unverified", "suspicious"):
            if v in vc:
                lines.append(f"| {v.upper()} | {vc[v]} |")

        lines.extend([
            "",
            "### Citation Roles",
            "| Role | Count |",
            "|------|-------|",
        ])
        for r in ("foundational", "data_source", "methodological", "contextual", "narrative", "secondary"):
            if r in rc:
                lines.append(f"| {r.upper()} | {rc[r]} |")

        lines.extend(["", "### Per-Reference Details", ""])
        for e in sorted(verified, key=lambda x: x.key):
            lines.append(f"#### {e.key}")
            lines.append(f"- Authors: {e.authors or '?'}")
            lines.append(f"- Year: {e.year or '?'}")
            lines.append(f"- Title: {(e.title or 'N/A')[:100]}")
            lines.append(f"- Cited by: {', '.join(e.cited_by)}")
            lines.append(f"- Role: {e.role or '?'}")
            lines.append(f"- Verdict: {e.verdict} ({e.verdict_confidence or '?'})")
            lines.append(f"- Evidence: {e.verdict_evidence or 'N/A'}")
            if e.crossref_doi:
                lines.append(f"- DOI (discovered): {e.crossref_doi}")
            lines.append("")

    # Citation consistency
    lines.extend(["", "## Citation Consistency Check"])
    lines.append("References cited in multiple papers with different formatting:")
    inconsistent = 0
    for e in entries.values():
        if len(e.raw_forms) > 1:
            raws = [rf["raw"][:100] for rf in e.raw_forms]
            if len(set(raws)) > 1:
                inconsistent += 1
                lines.append(f"\n### {e.key}")
                for rf in e.raw_forms:
                    lines.append(f"  - [{rf['source']}]: {rf['raw'][:120]}")
    if inconsistent == 0:
        lines.append("None found.")

    return "\n".join(lines)


def write_report(inv: Inventory, path: Path) -> None:
    """Write the Markdown audit report to a file."""
    report = generate_markdown(inv)
    path.write_text(report, encoding="utf-8")
