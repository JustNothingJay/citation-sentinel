# citation-sentinel

Open-source citation verification for independent researchers.

**citation-sentinel** audits academic papers by extracting references, looking them up on CrossRef and Open Library, validating DOIs, and flagging fabricated or suspicious citations.

Built from real-world audit experience: the SECS (Sovereign Engineering Computable Stack) project used this methodology to verify 285 references across 11 papers with zero fabrications detected.

---

## Why?

AI-generated papers can cite plausible-sounding references that don't exist. Traditional peer review doesn't systematically verify every citation. **citation-sentinel** automates full-spectrum verification:

| Step | What it does |
|------|-------------|
| **Extract** | Parse references from Markdown, LaTeX, and BibTeX files |
| **Discover** | Multi-strategy CrossRef search (author+title+year, title-only, author+journal, broad) |
| **Validate** | HTTP resolution of every DOI via doi.org |
| **Deep-verify** | Open Library fallback, context extraction, role classification, falsifiability verdict |
| **Report** | Markdown audit report + self-contained HTML dashboard |

## Installation

```bash
pip install citation-sentinel
```

Or from source:

```bash
git clone https://github.com/JustNothingJay/citation-sentinel.git
cd citation-sentinel
pip install -e .
```

Requires Python 3.10+.

## Quick Start

### Full audit (recommended)

```bash
sentinel audit ./my-papers/
```

This runs the entire pipeline and produces:
- `citation_inventory.json` — structured inventory of all references
- `citation_audit_report.md` — detailed Markdown report
- `citation_audit.html` — self-contained HTML dashboard

### Check a single reference

```bash
sentinel check "Einstein, A. (1905). On the Electrodynamics of Moving Bodies. Annalen der Physik."
```

### Step-by-step

```bash
# 1. Extract references
sentinel extract ./papers/ -o inventory.json

# 2. Look up DOIs via CrossRef
sentinel discover inventory.json --mailto you@example.com

# 3. Validate DOIs
sentinel validate inventory.json

# 4. Deep-verify references without DOI
sentinel deep-verify inventory.json --papers-dir ./papers/

# 5. Generate reports
sentinel report inventory.json -o report.md
sentinel dashboard inventory.json -o dashboard.html
```

## How It Works

### Extraction

Supports three input formats:

- **Markdown** — Detects reference sections by heading (`## References`, `## Bibliography`, etc.), then splits entries by numbered lists, bullets, table rows, or blank-line-separated paragraphs. Extracts DOIs, URLs, authors, year, title, and journal.
- **BibTeX** — Parses `@article{key, ...}` entries with proper field extraction.
- **LaTeX** — Detects `\bibliography{...}` / `\addbibresource{...}` and loads the referenced `.bib` files. Also parses `\bibitem{key}` entries directly.

### Discovery (CrossRef)

Four search strategies, tried in order:

1. **author+title+year** — Most specific. Uses bibliographic query with all available metadata.
2. **title-only** — Removes author constraint for papers with unusual name formatting.
3. **author+journal** — Finds papers when title is truncated or paraphrased.
4. **author+year (broad)** — Last resort. Searches by author surname and year.

Match scoring:
- **Title similarity** — Word-overlap ratio between query and result titles
- **Author bonus** (+0.15) — First author surname appears in CrossRef result
- **Year bonus** (+0.10) — Publication year matches
- **Journal bonus** (+0.10) — Journal name words overlap

Quality thresholds: `good` (≥ 0.60), `partial` (≥ 0.35), `poor` (> 0)

### Validation

Every discovered DOI is resolved via `https://doi.org/{doi}`:
- **2xx/3xx** → `passed` (DOI resolves to publisher)
- **403/406** → `paywall` (DOI exists but access restricted — still valid)
- **5xx/timeout** → `timeout` (network issue, not fabrication)
- **404/410** → `failed` (DOI doesn't resolve)

### Deep Verification

For references without DOI (books, conference proceedings, niche journals):
- Re-search CrossRef with alternative strategies
- Search Open Library (books API)
- Extract citation contexts from source papers
- Classify citation role (foundational, data source, methodological, contextual, narrative, secondary)
- Issue falsifiability verdict: `VERIFIED`, `LIKELY_REAL`, `UNVERIFIED`, `SUSPICIOUS`

### Verdicts

| Verdict | Meaning |
|---------|---------|
| `VERIFIED` | DOI resolved or strong CrossRef match + Open Library confirmation |
| `LIKELY_REAL` | Partial CrossRef match or Open Library hit |
| `UNVERIFIED` | No automated match found — may still be real (manual check needed) |
| `SUSPICIOUS` | Inconsistent metadata, patterns typical of fabrication |

## Community Verification Registry

**Status: Open design — contributions welcome.**

The sentinel pipeline produces structured, machine-readable audit data. A natural next step is a **shared registry** where researchers can upload their verification results and cross-reference against others.

### The Vision

Imagine a public database where:
- Independent researchers upload their `citation_inventory.json` after running an audit
- The registry cross-maps DOIs and reference keys across all submitted inventories
- References verified by multiple independent auditors gain a confidence score
- The system acts as an **automated peer reviewer for citation methodology**

This would let any researcher answer: *"Has anyone else verified this citation?"*

### Architecture Concept

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Researcher  │──────>│   sentinel   │──────>│ inventory.json│
│  runs audit  │       │   audit ./   │       │ (local)       │
└──────────────┘       └──────────────┘       └───────┬───────┘
                                                      │
                                        sentinel publish ──┐
                                                           │
                                              ┌────────────v────────────┐
                                              │   Community Registry    │
                                              │                         │
                                              │  • DOI cross-reference  │
                                              │  • Multi-audit verdicts │
                                              │  • Confidence scoring   │
                                              │  • Public API           │
                                              └─────────────────────────┘
```

### How To Build This

We designed sentinel so the registry can be built by anyone:

1. **Federated GitHub option** — Each researcher publishes their inventory JSON to a public repo; a GitHub Action aggregates them.
2. **Lightweight API option** — A serverless function (Cloudflare Workers, Vercel) accepting inventory uploads and serving cross-reference queries.
3. **Full database option** — PostgreSQL/SQLite backend with a web UI for browsing verified citations.

**We can't fund the database**, but the data format is stable and the `sentinel publish` command is designed to output registry-ready JSON. If you want to build this, open an issue.

### Contributing to the Registry

```bash
# Future: publish your audit results to a community registry
sentinel publish --registry https://registry.example.com

# Or export registry-compatible JSON
sentinel report inventory.json --format registry-json
```

## API Usage

```python
from sentinel.extract import extract_file
from sentinel.discover import discover_doi
from sentinel.validate import validate_doi

# Extract references from a paper
refs = extract_file("./my-paper.md")

# Look up a DOI
match = discover_doi(refs[0])
print(f"DOI: {match.doi}, quality: {match.quality}")

# Validate it
if match.doi:
    result = validate_doi(match.doi)
    print(f"Status: {result.status}")
```

## Configuration

All options are available as CLI flags. Key ones:

| Flag | Default | Description |
|------|---------|-------------|
| `--mailto` | `sentinel@example.com` | Email for CrossRef polite pool (faster responses) |
| `--delay` | `0.3` | Seconds between API calls |
| `--skip-validate` | off | Skip DOI HTTP validation |
| `--skip-deep` | off | Skip deep verification |

## Output Format

The `citation_inventory.json` is a structured file with:

```json
{
  "generated": "2026-03-21 10:00:00",
  "papers_scanned": 11,
  "total_references": 285,
  "entries": {
    "einstein_1905_electrodynamics": {
      "authors": "Einstein, A.",
      "year": "1905",
      "title": "On the Electrodynamics of Moving Bodies",
      "doi": "10.1002/andp.19053220607",
      "crossref_quality": "good",
      "crossref_score": 0.95,
      "validation_status": "passed",
      "verdict": "VERIFIED",
      "role": "FOUNDATIONAL",
      "cited_by": ["paper-01", "paper-03"]
    }
  }
}
```

## Accuracy

In our SECS audit (285 references, 11 papers):
- **208/285** DOIs discovered via CrossRef (73%)
- **215/215** DOIs validated via doi.org (100% — after paywall classification)
- **38/50** no-DOI references deep-verified as VERIFIED or LIKELY_REAL (76%)
- **0** suspicious citations (no fabrications)

### Known Limitations

- CrossRef coverage varies by discipline (humanities < STEM)
- Very old references (pre-1950) may not be in CrossRef
- Conference proceedings often lack DOIs
- Open Library mainly covers books, not journal articles
- The tool cannot verify the *content* of a citation — only that the cited work exists

## How This Project Works: AI + Human

This entire project — extraction, discovery, validation, classification, the CLI, the tests, the dashboard — was built and managed using AI coding tools. The pipeline runs autonomously end to end.

**But citation-sentinel does not replace the human.**

The machine does the exhaustive, tedious work: parsing every reference, querying every API, resolving every DOI, scoring every match. It catches the obvious fabrications and flags the ambiguous ones. What it cannot do is make the final judgement call on a reference that sits at the boundary.

The model is closer to **Wikipedia for independent research citations**:

1. **The machine builds the first draft** — automated extraction, lookup, verification
2. **The human reviews the output** — confirms verdicts, investigates edge cases, corrects false positives
3. **The verified result becomes the record** — once a human signs off, that citation is confirmed
4. **Over time, the machine learns from corrections** — human verdicts feed back into better matching

The goal is not AI replacing peer review. The goal is AI doing the 95% of citation verification that is mechanical, so the human can focus on the 5% that requires judgement.

**Every `sentinel audit` output should be reviewed by a human before being treated as authoritative.**

## Contributing: Collaborators, Not Forks

This is an open-source project that gets better through collaboration, not fragmentation.

**We want collaborators who contribute back**, not people who fork and disappear. The value of citation-sentinel scales with the community: more contributors means better extraction patterns, wider API coverage, stronger verification, and eventually a shared registry of verified citations.

### How to contribute

- **Fix a bug or improve accuracy?** Open a PR. We merge fast.
- **Found a reference format we don't handle?** Open an issue with a sample.
- **Built an integration?** (CI/CD, pre-commit hook, journal plugin) — share it.
- **Want to build the community registry?** Open an issue. We'll help design it.

Everyone who contributes improves the tool for every other user. Pull requests and issues are the mechanism. The MIT license means you *can* fork, but the benefit of contributing back is that everyone's sentinel gets better, not just yours.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built by Jay Carpenter as part of the [SECS project](https://secs.observer).

The verification methodology was developed and proven on 285 real-world academic citations across thermodynamics, mathematics, and engineering.

The "SECS Sentinel Verified" badge on [secs.observer/citation-audit.html](https://secs.observer/citation-audit.html) refers to the internal audit pipeline that preceded this open-source tool. The methodology is identical.
