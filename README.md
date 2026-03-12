# EA Handbook Compiler

[![Tests](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/test.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/test.yml)
[![Lint](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/lint.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/lint.yml)
[![Type Check](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/ty.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/ty.yml)
[![Build](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/build.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://www.python.org/)

A command-line tool that scrapes the
[EA Handbook](https://forum.effectivealtruism.org/handbook) and compiles it into
**Markdown**, **EPUB**, and **PDF** ebooks.

## Project Goals

- **Make EA content accessible offline** — produce high-quality ebook files from
  the Effective Altruism Handbook so readers can study the material on any device,
  anywhere, without an internet connection.
- **Keep the ebook up-to-date automatically** — a weekly CI pipeline scrapes the
  latest content, detects changes, and publishes a new
  [release](../../releases) when the handbook is updated.
- **Provide a clean, maintainable codebase** — strict linting, full type checking,
  and comprehensive tests make it easy for new contributors to jump in.

---

## Quick Start

### Requirements

| Tool | Purpose |
| --- | --- |
| Python ≥ 3.14 | Runtime |
| [uv](https://docs.astral.sh/uv/) | Dependency management |
| [pandoc](https://pandoc.org) | EPUB / PDF conversion |
| [weasyprint](https://weasyprint.org) *(optional)* | PDF engine (fallback: pdflatex) |

```bash
# macOS
brew install pandoc

# Ubuntu / Debian
sudo apt install pandoc weasyprint
```

### Installation

```bash
git clone https://github.com/kirilledition/EffectiveAltruismHandbook.git
cd EffectiveAltruismHandbook
uv sync
```

### Usage

```bash
# Full build: scrape → markdown → epub + pdf
uv run python -m eahandbookcompiler build --output-dir dist --verbose

# Scrape only (produces markdown)
uv run python -m eahandbookcompiler scrape --output-dir dist --verbose

# Convert an existing markdown file to epub + pdf
uv run python -m eahandbookcompiler convert dist/eahandbookcompiler.md --output-dir dist
```

Run `uv run python -m eahandbookcompiler --help` for all available options.

---

## Development

```bash
# Install all dependencies (including dev tools)
uv sync --dev

# Run the test suite
uv run pytest

# Run linter and formatter
uv run ruff check .
uv run ruff format .

# Run the type checker
uv run ty check .
```

### Project Layout

```
src/eahandbookcompiler/
├── __init__.py      # Package docstring
├── __main__.py      # Entry point for python -m
├── main.py          # CLI commands (click): build, scrape, convert
├── scraper.py       # Handbook/Post dataclasses, concurrent HTTP scraping
└── converter.py     # Markdown/EPUB/PDF generation, heading processing
tests/
├── test_main.py     # CLI command tests (click CliRunner)
├── test_scraper.py  # Scraping and HTML parsing tests
└── test_converter.py# Converter and heading logic tests
```

### CI Workflows

| Workflow | Trigger | What it does |
| --- | --- | --- |
| **test.yml** | Push / PR | Runs `pytest` with coverage |
| **lint.yml** | Push / PR | Runs Ruff formatter and linter |
| **ty.yml** | Push / PR | Runs the `ty` type checker |
| **build.yml** | Weekly (Sun 00:00 UTC) / manual | Scrapes, builds, and publishes a release |

All four checks must pass before a PR can be merged.

---

## Coding Conventions

This project follows strict, automated quality standards. All rules are enforced
by CI — if the checks pass, your code is good.

### Style & Formatting

- **Formatter / linter:** [Ruff](https://docs.astral.sh/ruff/) with
  `select = ["ALL"]` (all available rules enabled).
- **Line length:** 120 characters max.
- **Target:** Python 3.14+.
- Run `uv run ruff format .` and `uv run ruff check --fix .` before committing.

### Naming

- Use **descriptive, human-readable names** for all variables, parameters, and
  functions. Avoid single-letter names like `s`, `x`, `d`, or cryptic
  abbreviations like `pr`, `val`, `tmp`.
- **Functions and variables:** `snake_case` — e.g. `post_title`, `fetch_url`,
  `scraped_posts`.
- **Classes:** `PascalCase` — e.g. `Post`, `Handbook`.
- **Constants:** `UPPER_SNAKE_CASE` — e.g. `PDF_CSS`, `PANDOC_METADATA`.
- **Private helpers:** prefix with `_` — e.g. `_demote_line()`.

### Type Hints

- **All** function signatures must have type annotations (parameters and return
  type).
- Use `from __future__ import annotations` or `TYPE_CHECKING` guards where
  needed.
- The `ty` type checker runs in CI — your code must pass `uv run ty check .`
  with no errors.

### Docstrings

- Follow **Google style** ([example](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)).
- Every public module, class, and function needs a docstring.
- Include `Args`, `Returns`, and `Raises` sections when applicable.
- **Do not** repeat type information in docstrings — types belong in annotations.

```python
def fetch_post_content(post_url: str, *, timeout: int = 30) -> str:
    """Download and return the markdown body of a single post.

    Args:
        post_url: Full URL of the EA Forum post.
        timeout: HTTP request timeout in seconds.

    Returns:
        The post body converted to markdown.

    Raises:
        requests.HTTPError: If the server returns a non-2xx status.
    """
```

### Testing

- Write tests with **pytest**. Place them in `tests/`.
- Test file names mirror source files: `test_scraper.py` tests `scraper.py`.
- Use `unittest.mock.patch` to mock external calls (HTTP, filesystem, subprocess).
- Tests do **not** require docstrings or type annotations (relaxed via Ruff config).
- Run the suite: `uv run pytest`.

### General Guidelines

- Prefer **pathlib.Path** over `os.path` for file operations.
- Use **f-strings** for string formatting.
- Use **dataclasses** for plain data containers.
- Keep functions focused — each function should do one thing well.
- Add inline comments only when the *why* is not obvious from the code.

---

## Contributing

Contributions are welcome! Here is how to get started:

1. **Fork** the repository and create a feature branch from `main`.
2. **Set up** your environment:
   ```bash
   uv sync --dev
   ```
3. **Make your changes** — follow the [Coding Conventions](#coding-conventions)
   above.
4. **Run the checks locally** before pushing:
   ```bash
   uv run ruff format .        # auto-format
   uv run ruff check --fix .   # lint + auto-fix
   uv run ty check .           # type check
   uv run pytest               # tests
   ```
5. **Open a pull request** against `main`. All CI checks must pass.

> **Tip:** This repository uses auto-merge — once all four CI checks (tests,
> lint, type check, build) pass, your PR is merged automatically.

---

## License

[MIT](LICENSE)
