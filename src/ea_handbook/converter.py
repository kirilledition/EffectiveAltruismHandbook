"""Convert a Handbook to markdown, epub, and pdf via pandoc."""

import re
import shutil
import subprocess
from pathlib import Path

from ea_handbook.scraper import Handbook

HEADING_PATTERN = re.compile(r"^(?=#+ )", flags=re.MULTILINE)

PANDOC_METADATA = """\
---
title: "The Effective Altruism Handbook"
author: "Centre for Effective Altruism"
language: en
description: >
  A curated collection of posts from the EA Forum introducing the ideas
  and practices of Effective Altruism.
---

"""


def _build_metadata_page(
    handbook: Handbook,
    commit_hash: str = "",
    repo_url: str = "",
) -> str:
    """Build the metadata front page as a markdown string."""
    # Collect authors and dates
    authors: set[str] = set()
    dates: list[str] = []
    for post in handbook.posts:
        if post.author:
            authors.add(post.author)
        if post.posted_date:
            dates.append(post.posted_date)

    sorted_authors = sorted(authors, key=str.casefold)
    earliest = min(dates) if dates else "unknown"
    latest = max(dates) if dates else "unknown"

    # Build two-column author table
    rows: list[str] = []
    for i in range(0, len(sorted_authors), 2):
        left = sorted_authors[i]
        right = sorted_authors[i + 1] if i + 1 < len(sorted_authors) else ""
        rows.append(f"| {left} | {right} |")

    author_table = "| | |\n|---|---|\n" + "\n".join(rows) if rows else ""

    # Build info
    commit_part = f" with git commit `{commit_hash}`" if commit_hash else ""
    repo_url = repo_url or "https://github.com/kirilledition/EffectiveAltruismHandbook"

    parts = [
        "# About This Book\n\n",
        f"This book contains blog posts written from {earliest} to {latest} by:\n\n",
    ]
    if author_table:
        parts.append(f"{author_table}\n\n")
    parts.append("---\n\n")
    parts.append(
        f"*This ebook was compiled by Kirill Denisov using "
        f"[{repo_url.removeprefix('https://')}]({repo_url})"
        f"{commit_part}. "
        f"Last text update was on {latest}.*\n\n"
    )

    return "".join(parts)


def handbook_to_markdown(
    handbook: Handbook,
    output_path: Path,
    commit_hash: str = "",
    repo_url: str = "",
) -> Path:
    """
    Write the handbook to a single markdown file.

    Returns the path of the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [PANDOC_METADATA]

    # Insert metadata front page
    lines.append(_build_metadata_page(handbook, commit_hash=commit_hash, repo_url=repo_url))

    current_section: str | None = None

    for post in handbook.posts:
        if post.section and post.section != current_section:
            current_section = post.section
            lines.append(f"# {current_section}\n\n")

        lines.append(f"## {post.title}\n\n")

        if post.markdown:
            # Demote headings inside the post body so they nest under ## title
            demoted = _demote_headings(post.markdown)
            lines.append(demoted)
            lines.append("\n\n")
        else:
            lines.append(f"*See original post at: {post.url}*\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


def _demote_headings(text: str, levels: int = 2) -> str:
    """Increase all ATX heading levels by *levels* (e.g. # → ###)."""
    return HEADING_PATTERN.sub("#" * levels, text)


def _require_pandoc() -> str:
    """Return the path to pandoc, raising RuntimeError if not found."""
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError(
            "pandoc is not installed. "
            "Install it from https://pandoc.org/installing.html "
            "or via your system package manager."
        )
    return pandoc


def convert_to_epub(markdown_path: Path, output_path: Path) -> Path:
    """Convert the combined markdown file to epub using pandoc."""
    pandoc = _require_pandoc()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            pandoc,
            str(markdown_path),
            "--sandbox",
            "--from=markdown",
            "--to=epub3",
            f"--output={output_path}",
            "--toc",
            "--toc-depth=2",
            "--epub-chapter-level=2",
        ],
        check=True,
    )
    return output_path


def convert_to_pdf(markdown_path: Path, output_path: Path) -> Path:
    """Convert the combined markdown file to pdf using pandoc + pdflatex/weasyprint."""
    pandoc = _require_pandoc()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer weasyprint as pdf engine (no LaTeX needed in CI)
    pdf_engine = "weasyprint" if shutil.which("weasyprint") else "pdflatex"

    subprocess.run(
        [
            pandoc,
            str(markdown_path),
            "--sandbox",
            "--from=markdown",
            "--to=pdf",
            f"--pdf-engine={pdf_engine}",
            f"--output={output_path}",
            "--toc",
            "--toc-depth=2",
        ],
        check=True,
    )
    return output_path


def build_all(
    handbook: Handbook,
    output_dir: Path,
    commit_hash: str = "",
    repo_url: str = "",
) -> dict[str, Path]:
    """
    Build markdown, epub, and pdf from a Handbook.

    Returns a dict with keys 'markdown', 'epub', 'pdf'.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = handbook_to_markdown(
        handbook, output_dir / "ea-handbook.md",
        commit_hash=commit_hash, repo_url=repo_url,
    )
    epub_path = convert_to_epub(md_path, output_dir / "ea-handbook.epub")
    pdf_path = convert_to_pdf(md_path, output_dir / "ea-handbook.pdf")

    return {"markdown": md_path, "epub": epub_path, "pdf": pdf_path}
