"""
citation-sentinel CLI — the main entry point.

Usage:
    sentinel audit ./papers/              Full pipeline
    sentinel extract ./papers/            Extract only → inventory.json
    sentinel discover inventory.json      CrossRef DOI lookup
    sentinel validate inventory.json      DOI HTTP validation
    sentinel deep-verify inventory.json   Multi-strategy deep search
    sentinel report inventory.json        Generate Markdown report
    sentinel dashboard inventory.json     Generate HTML dashboard
    sentinel check "Author (Year). Title" Quick single-reference check
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from . import __version__


@click.group()
@click.version_option(__version__, prog_name="citation-sentinel")
def main() -> None:
    """Open-source citation verification for independent researchers."""


@main.command()
@click.argument("papers_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default="citation_inventory.json", help="Inventory output path")
@click.option("--globs", default=None, help="Comma-separated file globs (default: *.md,*.tex,*.bib)")
def extract(papers_dir: Path, output: str, globs: str | None) -> None:
    """Extract references from all papers in a directory."""
    from .extract import extract_all, find_papers
    from .inventory import Inventory

    glob_list = globs.split(",") if globs else None
    papers = find_papers(papers_dir, glob_list)
    click.echo(f"Found {len(papers)} paper files in {papers_dir}")

    inv = Inventory(
        generated=time.strftime("%Y-%m-%d %H:%M:%S"),
        papers_scanned=len(papers),
    )

    for paper in papers:
        refs = extract_all(paper.parent, [paper.name]) if paper.is_file() else []
        # If extract_all was given file's parent, extract from that file
        from .extract import extract_file
        refs = extract_file(paper)
        paper_name = paper.stem
        for ref in refs:
            inv.add_reference(ref, paper_name)

    inv.save(Path(output))
    click.echo(f"Extracted {len(inv.entries)} unique references → {output}")


@main.command()
@click.argument("inventory_file", type=click.Path(exists=True, path_type=Path))
@click.option("--mailto", default="citation-sentinel@example.com", help="Email for CrossRef polite pool")
@click.option("--delay", default=0.3, type=float, help="Seconds between API calls")
def discover(inventory_file: Path, mailto: str, delay: float) -> None:
    """Look up DOIs via CrossRef for references missing them."""
    from .discover import discover_doi, CrossRefMatch
    from .extract import Reference
    from .inventory import Inventory

    import httpx

    inv = Inventory.load(inventory_file)
    to_query = [e for e in inv.entries.values() if not e.doi]
    click.echo(f"Querying CrossRef for {len(to_query)} references without DOI...")

    found = 0
    poor = 0

    with httpx.Client(
        headers={"User-Agent": f"citation-sentinel/{__version__} (mailto:{mailto})"},
    ) as client:
        for i, entry in enumerate(to_query):
            ref = Reference(
                raw="",
                authors=entry.authors,
                year=entry.year,
                title=entry.title,
                journal=entry.journal,
                doi=entry.doi,
                key=entry.key,
            )
            match = discover_doi(ref, client=client, mailto=mailto, delay=delay)

            entry.crossref_quality = match.quality
            entry.crossref_score = match.score
            entry.crossref_strategy = match.strategy
            entry.crossref_title = match.title

            if match.doi and match.quality in ("good", "partial"):
                entry.doi = match.doi
                entry.crossref_doi = match.doi
                found += 1
            elif match.quality == "poor":
                entry.crossref_doi = match.doi
                poor += 1

            if (i + 1) % 10 == 0 or i + 1 == len(to_query):
                click.echo(f"  [{i + 1}/{len(to_query)}] found={found}, poor={poor}")

    inv.lookup_attempted = len(to_query)
    inv.lookup_found = found
    inv.lookup_poor = poor
    inv.save(inventory_file)
    click.echo(f"CrossRef lookup complete: {found} DOIs found, {poor} poor matches → {inventory_file}")


@main.command()
@click.argument("inventory_file", type=click.Path(exists=True, path_type=Path))
@click.option("--delay", default=0.5, type=float, help="Seconds between validation requests")
@click.option("--timeout", default=15.0, type=float, help="HTTP timeout in seconds")
def validate(inventory_file: Path, delay: float, timeout: float) -> None:
    """Validate DOIs by resolving them via doi.org."""
    from .validate import validate_batch, ValidationStatus
    from .inventory import Inventory

    inv = Inventory.load(inventory_file)
    dois = [e.doi for e in inv.entries.values() if e.doi]
    click.echo(f"Validating {len(dois)} DOIs...")

    def progress(i: int, total: int, doi: str, result) -> None:
        if i % 20 == 0 or i == total:
            click.echo(f"  [{i}/{total}] {result.status.value}")

    results = validate_batch(dois, delay=delay, timeout=timeout, progress_fn=progress)

    passed = 0
    failed = 0
    paywall = 0
    for doi, result in results.items():
        # Update inventory entries
        for entry in inv.entries.values():
            if entry.doi == doi:
                entry.validation_status = result.status.value
                entry.validation_http_code = result.http_code
                break
        if result.status == ValidationStatus.PASSED:
            passed += 1
        elif result.status == ValidationStatus.PAYWALL:
            paywall += 1
        else:
            failed += 1

    inv.validated_count = len(dois)
    inv.validated_passed = passed
    inv.validated_failed = failed
    inv.validated_paywall = paywall
    inv.save(inventory_file)
    click.echo(f"Validation complete: {passed} passed, {paywall} paywall, {failed} failed")


@main.command("deep-verify")
@click.argument("inventory_file", type=click.Path(exists=True, path_type=Path))
@click.option("--papers-dir", type=click.Path(exists=True, path_type=Path), default=None,
              help="Papers directory for context extraction")
@click.option("--mailto", default="citation-sentinel@example.com")
def deep_verify(inventory_file: Path, papers_dir: Path | None, mailto: str) -> None:
    """Deep-verify references without DOI using multi-strategy search."""
    from .discover import discover_doi, search_openlibrary, CrossRefMatch
    from .classify import classify_role, determine_verdict, extract_citation_context
    from .extract import Reference, first_author_surname
    from .inventory import Inventory
    import httpx

    inv = Inventory.load(inventory_file)
    no_doi = [e for e in inv.entries.values() if not e.doi]
    click.echo(f"Deep-verifying {len(no_doi)} references without DOI...")

    with httpx.Client(
        headers={"User-Agent": f"citation-sentinel/{__version__} (mailto:{mailto})"},
    ) as client:
        for i, entry in enumerate(no_doi):
            ref = Reference(
                raw="",
                authors=entry.authors,
                year=entry.year,
                title=entry.title,
                journal=entry.journal,
                key=entry.key,
            )

            # CrossRef deep search
            cr = discover_doi(ref, client=client, mailto=mailto, delay=0.3)

            # Open Library
            ol = search_openlibrary(ref, client=client)

            # Context extraction
            contexts: list[str] = []
            if papers_dir:
                surname = first_author_surname(entry.authors)
                for paper_name in entry.cited_by:
                    # Try to find the paper file
                    for p in papers_dir.rglob(f"*{paper_name}*"):
                        if p.suffix in (".md", ".tex"):
                            contexts.extend(
                                extract_citation_context(p, surname, entry.year)
                            )
                            break

            # Role classification
            role = classify_role(contexts, entry.title)

            # Verdict
            classification = determine_verdict(
                crossref_found=cr.found,
                crossref_quality=cr.quality,
                crossref_doi=cr.doi,
                openlibrary_found=ol.found,
            )
            classification.role = role

            # Update entry
            entry.crossref_quality = cr.quality
            entry.crossref_score = cr.score
            entry.crossref_strategy = cr.strategy
            entry.crossref_title = cr.title
            entry.crossref_doi = cr.doi
            entry.openlibrary_found = ol.found
            entry.verdict = classification.verdict.value
            entry.verdict_confidence = classification.confidence
            entry.verdict_evidence = classification.evidence
            entry.role = role.value
            entry.contexts = contexts[:3]

            if cr.doi and cr.quality in ("good", "partial"):
                entry.doi = cr.doi

            click.echo(f"  [{i + 1}/{len(no_doi)}] {entry.key}: "
                       f"{classification.verdict.value} ({cr.quality})")

    inv.save(inventory_file)
    click.echo(f"Deep verification complete → {inventory_file}")


@main.command()
@click.argument("inventory_file", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default="citation_audit_report.md", help="Report output path")
def report(inventory_file: Path, output: str) -> None:
    """Generate a Markdown audit report."""
    from .report import write_report
    from .inventory import Inventory

    inv = Inventory.load(inventory_file)
    write_report(inv, Path(output))
    click.echo(f"Report written → {output}")


@main.command()
@click.argument("inventory_file", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default="citation_audit.html", help="Dashboard output path")
def dashboard(inventory_file: Path, output: str) -> None:
    """Generate a self-contained HTML verification dashboard."""
    from .dashboard import write_dashboard
    from .inventory import Inventory

    inv = Inventory.load(inventory_file)
    write_dashboard(inv, Path(output))
    click.echo(f"Dashboard written → {output}")


@main.command()
@click.argument("papers_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", default="citation_inventory.json", help="Inventory output path")
@click.option("--report-path", default="citation_audit_report.md", help="Report output path")
@click.option("--dashboard-path", default="citation_audit.html", help="Dashboard output path")
@click.option("--mailto", default="citation-sentinel@example.com", help="Email for CrossRef")
@click.option("--skip-validate", is_flag=True, help="Skip DOI validation (faster)")
@click.option("--skip-deep", is_flag=True, help="Skip deep verification")
def audit(
    papers_dir: Path,
    output: str,
    report_path: str,
    dashboard_path: str,
    mailto: str,
    skip_validate: bool,
    skip_deep: bool,
) -> None:
    """Full audit pipeline: extract → discover → validate → deep-verify → report."""
    from .extract import extract_file, find_papers
    from .inventory import Inventory
    from .discover import discover_doi, search_openlibrary
    from .classify import classify_role, determine_verdict, extract_citation_context
    from .extract import Reference, first_author_surname
    from .validate import validate_batch, ValidationStatus
    from .report import write_report
    from .dashboard import write_dashboard
    import httpx

    # 1. Extract
    papers = find_papers(papers_dir)
    click.echo(f"[1/5] Extracting references from {len(papers)} papers...")
    inv = Inventory(
        generated=time.strftime("%Y-%m-%d %H:%M:%S"),
        papers_scanned=len(papers),
    )
    for paper in papers:
        refs = extract_file(paper)
        paper_name = paper.stem
        for ref in refs:
            inv.add_reference(ref, paper_name)
    click.echo(f"  → {len(inv.entries)} unique references extracted")

    # 2. Discover DOIs
    to_query = [e for e in inv.entries.values() if not e.doi]
    click.echo(f"[2/5] CrossRef lookup for {len(to_query)} references without DOI...")
    found = 0
    poor = 0
    with httpx.Client(
        headers={"User-Agent": f"citation-sentinel/{__version__} (mailto:{mailto})"},
    ) as client:
        for i, entry in enumerate(to_query):
            ref = Reference(
                raw="",
                authors=entry.authors,
                year=entry.year,
                title=entry.title,
                journal=entry.journal,
                key=entry.key,
            )
            match = discover_doi(ref, client=client, mailto=mailto, delay=0.3)
            entry.crossref_quality = match.quality
            entry.crossref_score = match.score
            entry.crossref_strategy = match.strategy
            entry.crossref_title = match.title
            if match.doi and match.quality in ("good", "partial"):
                entry.doi = match.doi
                entry.crossref_doi = match.doi
                found += 1
            elif match.quality == "poor":
                entry.crossref_doi = match.doi
                poor += 1
            if (i + 1) % 20 == 0 or i + 1 == len(to_query):
                click.echo(f"  [{i + 1}/{len(to_query)}] found={found}")
    inv.lookup_attempted = len(to_query)
    inv.lookup_found = found
    inv.lookup_poor = poor
    click.echo(f"  → {found} DOIs found, {poor} poor matches")

    # 3. Validate DOIs
    if not skip_validate:
        dois = [e.doi for e in inv.entries.values() if e.doi]
        click.echo(f"[3/5] Validating {len(dois)} DOIs via doi.org...")
        results = validate_batch(dois, delay=0.5, progress_fn=lambda i, t, d, r: (
            click.echo(f"  [{i}/{t}]") if i % 20 == 0 or i == t else None
        ))
        passed = sum(1 for r in results.values() if r.status == ValidationStatus.PASSED)
        paywall = sum(1 for r in results.values() if r.status == ValidationStatus.PAYWALL)
        failed = sum(1 for r in results.values() if r.status not in (ValidationStatus.PASSED, ValidationStatus.PAYWALL))
        for doi, result in results.items():
            for entry in inv.entries.values():
                if entry.doi == doi:
                    entry.validation_status = result.status.value
                    entry.validation_http_code = result.http_code
                    break
        inv.validated_count = len(dois)
        inv.validated_passed = passed
        inv.validated_failed = failed
        inv.validated_paywall = paywall
        click.echo(f"  → {passed} passed, {paywall} paywall, {failed} failed")
    else:
        click.echo("[3/5] Skipped DOI validation")

    # 4. Deep verification
    if not skip_deep:
        no_doi = [e for e in inv.entries.values() if not e.doi]
        click.echo(f"[4/5] Deep-verifying {len(no_doi)} references...")
        with httpx.Client(
            headers={"User-Agent": f"citation-sentinel/{__version__} (mailto:{mailto})"},
        ) as client:
            for i, entry in enumerate(no_doi):
                ref = Reference(
                    raw="",
                    authors=entry.authors,
                    year=entry.year,
                    title=entry.title,
                    journal=entry.journal,
                    key=entry.key,
                )
                cr = discover_doi(ref, client=client, mailto=mailto, delay=0.3)
                ol = search_openlibrary(ref, client=client)
                contexts: list[str] = []
                surname = first_author_surname(entry.authors)
                for paper_name in entry.cited_by:
                    for p in papers_dir.rglob(f"*{paper_name}*"):
                        if p.suffix in (".md", ".tex", ".bib"):
                            contexts.extend(
                                extract_citation_context(p, surname, entry.year)
                            )
                            break
                role = classify_role(contexts, entry.title)
                classification = determine_verdict(
                    crossref_found=cr.found,
                    crossref_quality=cr.quality,
                    crossref_doi=cr.doi,
                    openlibrary_found=ol.found,
                )
                entry.crossref_quality = cr.quality
                entry.crossref_score = cr.score
                entry.crossref_strategy = cr.strategy
                entry.crossref_title = cr.title
                entry.crossref_doi = cr.doi
                entry.openlibrary_found = ol.found
                entry.verdict = classification.verdict.value
                entry.verdict_confidence = classification.confidence
                entry.verdict_evidence = classification.evidence
                entry.role = role.value
                entry.contexts = contexts[:3]
                if cr.doi and cr.quality in ("good", "partial"):
                    entry.doi = cr.doi
                click.echo(f"  [{i + 1}/{len(no_doi)}] {entry.key}: {classification.verdict.value}")
    else:
        click.echo("[4/5] Skipped deep verification")

    # 5. Reports
    click.echo("[5/5] Generating reports...")
    inv.save(Path(output))
    write_report(inv, Path(report_path))
    write_dashboard(inv, Path(dashboard_path))
    click.echo(f"  → {output}")
    click.echo(f"  → {report_path}")
    click.echo(f"  → {dashboard_path}")
    click.echo("")

    # Final summary
    total = len(inv.entries)
    suspicious = sum(1 for e in inv.entries.values() if e.verdict == "suspicious")
    if suspicious == 0:
        click.secho("RESULT: Zero fabrications detected.", fg="green", bold=True)
    else:
        click.secho(f"WARNING: {suspicious} suspicious references found.", fg="red", bold=True)


@main.command()
@click.argument("reference", type=str)
@click.option("--mailto", default="citation-sentinel@example.com")
def check(reference: str, mailto: str) -> None:
    """Quick check: is a single reference real?

    Example: sentinel check "Banach, S. (1922). Sur les opérations..."
    """
    from .extract import _parse_md_entry
    from .discover import discover_doi, search_openlibrary

    ref = _parse_md_entry(reference)
    click.echo(f"Parsed: {ref.authors or '?'} ({ref.year or '?'}) — {(ref.title or 'N/A')[:60]}")

    click.echo("Searching CrossRef...")
    cr = discover_doi(ref, mailto=mailto, delay=0)

    if cr.found and cr.quality in ("good", "partial"):
        click.secho(f"FOUND: {cr.title[:80]}", fg="green")
        if cr.doi:
            click.echo(f"  DOI: https://doi.org/{cr.doi}")
        click.echo(f"  Quality: {cr.quality} (score: {cr.score})")
        click.echo(f"  Strategy: {cr.strategy}")
    else:
        click.echo("Not found in CrossRef. Trying Open Library...")
        ol = search_openlibrary(ref)
        if ol.found:
            click.secho(f"FOUND (book): {ol.title}", fg="green")
            click.echo(f"  Authors: {ol.authors}")
        else:
            click.secho("NOT FOUND in CrossRef or Open Library.", fg="yellow")
            click.echo("  This may be a book, conference proceedings, or niche publication.")
            click.echo("  Manual verification recommended.")


if __name__ == "__main__":
    main()
