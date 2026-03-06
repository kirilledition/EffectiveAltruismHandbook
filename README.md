# EffectiveAltruismHandbook

[![Build Status](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/build.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/build.yml)
[![Lint Status](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/lint.yml/badge.svg)](https://github.com/kirilledition/EffectiveAltruismHandbook/actions/workflows/lint.yml)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/kirilledition/GIST_ID/raw/coverage.json)


A [uv](https://docs.astral.sh/uv/)-based Python tool that scrapes posts from the
[EA Handbook](https://forum.effectivealtruism.org/handbook) and compiles them into
a single **Markdown**, **EPUB**, and **PDF** ebook.

Releases are published automatically by GitHub Actions every week and are available
on the [Releases page](../../releases).

---

## Requirements

| Tool                                              | Purpose                         |
| ------------------------------------------------- | ------------------------------- |
| Python ≥ 3.14                                     | Runtime                         |
| [uv](https://docs.astral.sh/uv/)                  | Dependency management           |
| [pandoc](https://pandoc.org)                      | EPUB / PDF conversion           |
| [weasyprint](https://weasyprint.org) *(optional)* | PDF engine (fallback: pdflatex) |

Install pandoc via your package manager, e.g.:

```bash
# macOS
brew install pandoc

# Ubuntu / Debian
sudo apt install pandoc weasyprint
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/kirilledition/EffectiveAltruismHandbook.git
cd EffectiveAltruismHandbook

# Install with uv
uv sync
```

---

## Usage

### Build everything (markdown + epub + pdf)

```bash
uv run python -m eahandbookcompiler build --output-dir dist --verbose
```

### Scrape only (markdown output)

```bash
uv run python -m eahandbookcompiler scrape --output-dir dist --verbose
```

### Convert an existing markdown file

```bash
uv run python -m eahandbookcompiler convert dist/eahandbookcompiler.md --output-dir dist
```

### Options

```
Options:
  --output-dir, -o  Directory for output files  [default: dist]
  --delay, -d       Seconds between HTTP requests  [default: 1.0]
  --verbose, -v     Print progress information
  --help            Show help message and exit
```

---

## Development

```bash
# Install including dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run the CLI from source
uv run python -m eahandbookcompiler --help
```

---

## GitHub Actions

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `test.yml` | Push to `main`, PRs | Runs the test suite and updates the coverage badge |
| `lint.yml` | Push to `main`, PRs | Runs Ruff formatter/linter and auto-commits fixes |
| `ty.yml` | Push to `main`, PRs | Runs the `ty` type checker |
| `build.yml` | Weekly (Sun 00:00 UTC), manual | Scrapes, builds, and releases the ebook |
| `update-dependencies.yml` | Manual | Updates uv lockfile, Actions versions, and Python patch version |

### Coverage badge setup

The coverage badge is rendered dynamically via [shields.io](https://shields.io)
and backed by a GitHub Gist (no files are committed to the repo). One-time setup:

1. Create a **public** GitHub Gist (any filename, e.g. `coverage.json`).
2. Copy the **Gist ID** from its URL.
3. Create a GitHub **Personal Access Token** with the `gist` scope.
4. In the repository, add:
   - **Secret** `GIST_SECRET` — the PAT created above.
   - **Variable** `COVERAGE_GIST_ID` — the Gist ID.
5. Update the badge URL in this README, replacing `GIST_ID` with your Gist ID.
