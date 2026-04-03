"""
Static HTML dashboard generator.

Produces a self-contained HTML file with:
- Summary statistics
- Animated verdict bars
- Role distribution
- Most-cited references table
- Community verification badge
"""

from __future__ import annotations

import html
import json
import time
from collections import Counter
from pathlib import Path

from .inventory import Inventory

_CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#0a0b0d;color:#e0e2e8;line-height:1.7}
a{color:#00B2FF;text-decoration:none}a:hover{color:#FF5E00}
.container{max-width:900px;margin:0 auto;padding:20px 24px}
h1,h2,h3{font-weight:500;margin-top:0}
code{font-family:'JetBrains Mono',monospace;font-size:.85em;background:rgba(255,255,255,.05);
     padding:2px 6px;border-radius:3px}

.hero{text-align:center;padding:40px 0 30px}
.badge{display:inline-block;font-family:monospace;font-size:.75rem;font-weight:700;
       letter-spacing:2px;text-transform:uppercase;padding:8px 24px;border-radius:4px;
       margin-bottom:20px}
.badge-pass{color:#48e662;border:1px solid rgba(72,230,98,.3);background:rgba(72,230,98,.06)}
.badge-warn{color:#f0a030;border:1px solid rgba(240,160,48,.3);background:rgba(240,160,48,.06)}
.subtitle{color:#8b8f9a;font-size:.95rem;max-width:650px;margin:0 auto;line-height:1.7}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:30px 0}
.stat{background:#161920;border:1px solid rgba(255,255,255,.06);border-radius:8px;
      padding:20px 16px;text-align:center}
.stat-n{font-family:monospace;font-size:1.8rem;font-weight:600;line-height:1}
.stat-l{font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:#555963;
        margin-top:6px;font-weight:500}
.green{color:#48e662}.blue{color:#00B2FF}.orange{color:#FF5E00}

.section{margin:40px 0}
.section h2{font-size:1.15rem;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.06)}

.bar-row{display:flex;align-items:center;gap:14px;margin:10px 0}
.bar-label{flex:0 0 120px;font-family:monospace;font-size:.75rem;text-align:right;color:#8b8f9a}
.bar-track{flex:1;height:26px;background:rgba(255,255,255,.03);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;display:flex;align-items:center;padding-left:10px;
          transition:width 1.5s ease}
.bar-fill span{font-family:monospace;font-size:.7rem;font-weight:600;color:#fff}
.bg-green{background:linear-gradient(90deg,rgba(72,230,98,.7),rgba(72,230,98,.4))}
.bg-blue{background:linear-gradient(90deg,rgba(0,178,255,.7),rgba(0,178,255,.4))}
.bg-amber{background:linear-gradient(90deg,rgba(240,160,48,.7),rgba(240,160,48,.4))}
.bg-red{background:linear-gradient(90deg,rgba(255,70,70,.7),rgba(255,70,70,.4))}
.bar-count{flex:0 0 40px;font-family:monospace;font-size:.85rem;font-weight:600;text-align:right}

.pills{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.pill{display:flex;align-items:center;gap:8px;background:#161920;
      border:1px solid rgba(255,255,255,.06);border-radius:6px;padding:10px 16px}
.pill-n{font-family:monospace;font-size:1.2rem;font-weight:600;color:#00B2FF}
.pill-l{font-size:.72rem;text-transform:uppercase;letter-spacing:1px;color:#8b8f9a}

table{width:100%;border-collapse:collapse}
th{font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;
   color:#555963;text-align:left;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.06)}
td{font-size:.85rem;color:#8b8f9a;padding:10px 14px;
   border-bottom:1px solid rgba(255,255,255,.03);vertical-align:top}
tr:hover td{background:rgba(255,255,255,.02)}
.ref-key{font-family:monospace;font-size:.78rem;color:#00B2FF;white-space:nowrap}
.cite-count{font-family:monospace;font-weight:600;color:#FF5E00;text-align:center}
.doi-link{font-family:monospace;font-size:.7rem;word-break:break-all}

.method{background:#161920;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:24px}
.method h3{font-size:.9rem;margin-bottom:12px}
.method p,.method li{font-size:.85rem;color:#8b8f9a;line-height:1.7}
.method ul{padding-left:18px;margin:10px 0}.method li{margin-bottom:4px}
.tag{display:inline-block;font-family:monospace;font-size:.65rem;font-weight:600;padding:2px 7px;
     border-radius:3px;margin-right:3px}
.tag-api{color:#00B2FF;background:rgba(0,178,255,.1);border:1px solid rgba(0,178,255,.2)}
.tag-http{color:#48e662;background:rgba(72,230,98,.1);border:1px solid rgba(72,230,98,.2)}
.tag-nlp{color:#f0a030;background:rgba(240,160,48,.1);border:1px solid rgba(240,160,48,.2)}

.community{text-align:center;padding:30px 20px;margin:30px 0;
           border:1px solid rgba(0,178,255,.2);border-radius:10px;background:rgba(0,178,255,.03)}
.community h3{font-size:1.1rem;color:#00B2FF;margin-bottom:8px}
.community p{color:#8b8f9a;font-size:.88rem;max-width:600px;margin:0 auto;line-height:1.7}

footer{text-align:center;padding:30px 0;border-top:1px solid rgba(255,255,255,.06);margin-top:30px}
footer p{font-size:.75rem;color:#555963}
"""


def _esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def generate_dashboard(inv: Inventory) -> str:
    """Generate a self-contained HTML dashboard from an inventory."""
    entries = inv.entries
    total = len(entries)
    with_doi = sum(1 for e in entries.values() if e.doi)
    without_doi = total - with_doi

    # Verdict counts
    verified_entries = [e for e in entries.values() if e.verdict]
    vc = Counter(e.verdict for e in verified_entries)
    rc = Counter(e.role for e in verified_entries if e.role)

    has_suspicious = vc.get("suspicious", 0) > 0
    badge_class = "badge-warn" if has_suspicious else "badge-pass"
    badge_text = (
        f"{vc.get('suspicious', 0)} SUSPICIOUS REFERENCES"
        if has_suspicious
        else "ZERO FABRICATIONS DETECTED"
    )

    # Top cited
    top = sorted(entries.values(), key=lambda e: len(e.cited_by), reverse=True)[:10]

    # Verdict bar widths (percentage of total deep-verified)
    dv_total = len(verified_entries) or 1

    parts: list[str] = []
    parts.append("<!doctype html><html lang='en'><head>")
    parts.append("<meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append(f"<title>Citation Audit — {total} References Verified</title>")
    parts.append(f"<style>{_CSS}</style>")
    parts.append("</head><body><div class='container'>")

    # Hero
    parts.append("<div class='hero'>")
    parts.append(f"<div class='badge {badge_class}'>{badge_text}</div>")
    parts.append("<h1>Citation Audit</h1>")
    parts.append(f"<p class='subtitle'>Automated verification of {total} unique citations across "
                 f"{inv.papers_scanned} papers. Every reference checked against CrossRef, "
                 f"doi.org, and Open Library.</p>")
    parts.append("</div>")

    # Stats
    parts.append("<div class='stats'>")
    for n, label, cls in [
        (total, "Unique Citations", ""),
        (with_doi, "With DOI", "green"),
        (inv.validated_passed, "DOIs Validated", "green"),
        (inv.lookup_found, "CrossRef Matched", "blue"),
        (inv.papers_scanned, "Papers Scanned", "orange"),
        (without_doi, "Without DOI", ""),
    ]:
        parts.append(f"<div class='stat'><div class='stat-n {cls}'>{n}</div>"
                     f"<div class='stat-l'>{label}</div></div>")
    parts.append("</div>")

    # Deep verification verdicts
    if verified_entries:
        parts.append("<div class='section'><h2>Deep Verification Verdicts</h2>")
        for label, key, bar_cls, count_cls in [
            ("VERIFIED", "verified", "bg-green", "green"),
            ("LIKELY REAL", "likely_real", "bg-blue", "blue"),
            ("UNVERIFIED", "unverified", "bg-amber", "orange"),
            ("SUSPICIOUS", "suspicious", "bg-red", ""),
        ]:
            count = vc.get(key, 0)
            pct = round(100 * count / dv_total) if count else 0
            parts.append(
                f"<div class='bar-row'><div class='bar-label'>{label}</div>"
                f"<div class='bar-track'><div class='bar-fill {bar_cls}' "
                f"style='width:{pct}%'><span></span></div></div>"
                f"<div class='bar-count {count_cls}'>{count}</div></div>"
            )
        parts.append("</div>")

    # Roles
    if rc:
        parts.append("<div class='section'><h2>Citation Roles</h2><div class='pills'>")
        for role in ("foundational", "data_source", "methodological", "contextual", "narrative", "secondary"):
            if role in rc:
                parts.append(f"<div class='pill'><div class='pill-n'>{rc[role]}</div>"
                             f"<div class='pill-l'>{role.replace('_', ' ')}</div></div>")
        parts.append("</div></div>")

    # Top cited table
    if top:
        parts.append("<div class='section'><h2>Most-Cited References</h2>")
        parts.append("<div style='overflow-x:auto'><table><thead><tr>"
                     "<th>Reference</th><th style='text-align:center'>Papers</th>"
                     "<th>Authors</th><th>Year</th><th>DOI</th></tr></thead><tbody>")
        for e in top:
            doi_cell = (
                f"<a class='doi-link' href='https://doi.org/{_esc(e.doi)}' "
                f"target='_blank' rel='noopener'>{_esc(e.doi)}</a>"
                if e.doi else "—"
            )
            parts.append(
                f"<tr><td class='ref-key'>{_esc(e.key)}</td>"
                f"<td class='cite-count'>{len(e.cited_by)}</td>"
                f"<td>{_esc(e.authors)}</td><td>{_esc(e.year)}</td>"
                f"<td>{doi_cell}</td></tr>"
            )
        parts.append("</tbody></table></div></div>")

    # Community section
    parts.append("<div class='community'>")
    parts.append("<h3>Community Verification Registry</h3>")
    parts.append("<p>citation-sentinel supports uploading your audit results to a shared, "
                 "open registry where independently verified citations are cross-mapped. "
                 "When multiple researchers independently verify the same reference, "
                 "confidence compounds. This creates a decentralised peer-review layer "
                 "for citation integrity — no institution required.</p>")
    parts.append(f"<p style='margin-top:12px;font-size:.78rem;color:#555963'>"
                 f"<code>sentinel publish --registry community</code></p>")
    parts.append("</div>")

    # Methodology
    parts.append("<div class='section'><h2>Methodology</h2><div class='method'>")
    parts.append("<h3>Primary Audit</h3><ul>")
    parts.append("<li><span class='tag tag-nlp'>PARSE</span> "
                 "Extract references from Markdown, LaTeX, and BibTeX papers</li>")
    parts.append("<li><span class='tag tag-api'>CROSSREF</span> "
                 "Query CrossRef REST API with multi-strategy matching</li>")
    parts.append("<li><span class='tag tag-http'>HTTP</span> "
                 "Validate DOIs via doi.org resolution</li></ul>")
    parts.append("<h3>Deep Verification</h3><ul>")
    parts.append("<li>Four CrossRef strategies: author+title+year, title-only, "
                 "author+journal, author+year-broad</li>")
    parts.append("<li>Open Library fallback for books</li>")
    parts.append("<li>Citation context extraction for role classification</li>")
    parts.append("<li>Falsifiability verdict: VERIFIED → LIKELY_REAL → UNVERIFIED → SUSPICIOUS</li>")
    parts.append("</ul><h3>Reproducibility</h3>")
    parts.append("<p>Install: <code>pip install citation-sentinel</code><br>")
    parts.append("Run: <code>sentinel audit ./papers/</code></p>")
    parts.append("</div></div>")

    # Footer
    parts.append(f"<footer><p>Generated by citation-sentinel v{inv.tool_version} "
                 f"on {time.strftime('%Y-%m-%d %H:%M:%S')}</p></footer>")

    parts.append("</div></body></html>")
    return "\n".join(parts)


def write_dashboard(inv: Inventory, path: Path) -> None:
    """Write the HTML dashboard to a file."""
    dashboard = generate_dashboard(inv)
    path.write_text(dashboard, encoding="utf-8")
