# Contributing to citation-sentinel

Thanks for your interest in improving citation verification for independent research.

**I want collaborators, not forks.** The value of this tool scales with the community — every improvement you contribute makes sentinel better for every other user. Fork if you must, but contributing back through PRs and issues is how the ecosystem grows.

## Setup

```bash
git clone https://github.com/JustNothingJay/citation-sentinel.git
cd citation-sentinel
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

## Tests

```bash
pytest -v
```

All tests must pass before submitting a PR.

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting:

```bash
ruff check .
ruff format .
```

## What I Need Help With

### Extraction Accuracy
- Better parsing of unusual reference formats (e.g., footnote-style, endnote exports)
- Support for RIS, EndNote XML, and CSL-JSON import
- Edge cases in BibTeX parsing (nested braces, string concatenation)

### Discovery Coverage
- Additional APIs beyond CrossRef and Open Library (Semantic Scholar, DBLP, PubMed)
- Better matching for non-English titles
- Conference proceedings discovery (ACM DL, IEEE Xplore metadata)

### Community Registry
This is the big one. A shared verification database where researchers can upload and cross-reference their audit results. See the README for architecture concepts. Options:
- Federated GitHub-based aggregation
- Lightweight serverless API
- Full database with web UI

The data format is stable and the tool is designed to produce registry-ready output. If you want to take this on, open an issue.

### Documentation
- Tutorials for specific disciplines (humanities, STEM, social science)
- Integration guides (CI/CD, pre-commit hooks, journal submission workflows)

## Submitting Changes

1. Fork the repo
2. Create a feature branch: `git checkout -b my-feature`
3. Make your changes
4. Run `pytest -v` and `ruff check .`
5. Submit a PR with a clear description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
