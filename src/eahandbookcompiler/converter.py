"""Convert a Handbook to markdown, epub, and pdf via pandoc."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eahandbookcompiler.scraper import Handbook

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


def build_metadata_page(
    handbook: Handbook,
    commit_hash: str = "",
    repo_url: str = "",
) -> str:
    """Build the metadata front page as a markdown string.

    The page includes the date range of posts, a two-column alphabetised
    author table, and compiler / repository attribution.

    Args:
        handbook: Handbook whose posts supply author and date information.
        commit_hash: Git commit hash to embed in the attribution line.
        repo_url: Repository URL for the attribution link.

    Returns:
        Markdown string suitable for inserting at the start of the book.
    """
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
        f"Last text update was on {latest}.*\n\n",
    )

    return "".join(parts)


def handbook_to_markdown(
    handbook: Handbook,
    output_path: Path,
    commit_hash: str = "",
    repo_url: str = "",
) -> Path:
    """Write the handbook to a single combined markdown file.

    Each post is rendered under its section heading with demoted internal
    headings so the document hierarchy stays consistent.

    Args:
        handbook: Populated ``Handbook`` with post content.
        output_path: Destination file path (parent dirs created automatically).
        commit_hash: Git commit hash forwarded to the metadata page.
        repo_url: Repository URL forwarded to the metadata page.

    Returns:
        The resolved path of the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [PANDOC_METADATA]

    # Insert metadata front page
    lines.append(build_metadata_page(handbook, commit_hash=commit_hash, repo_url=repo_url))

    current_section: str | None = None

    for post in handbook.posts:
        if post.section and post.section != current_section:
            current_section = post.section
            lines.append(f"# {current_section}\n\n")

        lines.append(f"## {post.title}\n\n")

        if post.markdown:
            # Demote headings inside the post body so they nest under ## title
            demoted = demote_headings(post.markdown)
            lines.append(demoted)
            lines.append("\n\n")
        else:
            lines.append(f"*See original post at: {post.url}*\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


def demote_headings(text: str, levels: int = 2) -> str:
    """Increase all ATX heading levels by *levels*, ignoring code blocks.

    For example, with ``levels=2`` a ``# Heading`` becomes ``### Heading``.
    Headings inside fenced code blocks (backtick or tilde) are left
    untouched.

    Args:
        text: Markdown text to process.
        levels: Number of ``#`` characters to prepend.

    Returns:
        Markdown text with headings demoted.
    """
    result: list[str] = []
    in_code_block = False
    code_block_marker: str | None = None

    for line in text.splitlines():
        # Check if we are toggling a code block
        match = re.match(r"^(```|~~~)", line.strip())
        if match:
            marker = match.group(1)
            if not in_code_block:
                in_code_block = True
                code_block_marker = marker
            elif marker == code_block_marker:
                in_code_block = False
                code_block_marker = None
            result.append(line)
            continue

        if not in_code_block and re.match(r"^#+ ", line):
            result.append("#" * levels + line)
        else:
            result.append(line)

    return "\n".join(result)


def require_pandoc() -> str:
    """Return the path to the ``pandoc`` executable.

    Raises:
        RuntimeError: If pandoc is not found on ``$PATH``.
    """
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError(
            "pandoc is not installed. "
            "Install it from https://pandoc.org/installing.html "
            "or via your system package manager.",
        )
    return pandoc


def convert_to_epub(markdown_path: Path, output_path: Path) -> Path:
    """Convert a combined markdown file to EPUB 3 using pandoc.

    Args:
        markdown_path: Path to the source markdown file.
        output_path: Desired output ``.epub`` path.

    Returns:
        The resolved output path.

    Raises:
        RuntimeError: If pandoc is not installed.
        subprocess.CalledProcessError: If pandoc exits with an error.
    """
    pandoc = require_pandoc()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Workaround for nixpkgs pandoc missing epub.css
    dummy_css = output_path.parent / "epub.css"
    if not dummy_css.exists():
        dummy_css.write_text("/* Custom EPUB CSS */\n", encoding="utf-8")

    subprocess.run(
        [
            pandoc,
            str(markdown_path),
            "--from=markdown",
            "--to=epub3",
            f"--output={output_path}",
            "--toc",
            "--toc-depth=2",
            "--split-level=2",
            f"--css={dummy_css}",
        ],
        check=True,
    )
    return output_path


def convert_to_pdf(markdown_path: Path, output_path: Path) -> Path:
    """Convert a combined markdown file to PDF using pandoc.

    Prefers ``weasyprint`` as the PDF engine when available; falls back
    to ``pdflatex``.

    Args:
        markdown_path: Path to the source markdown file.
        output_path: Desired output ``.pdf`` path.

    Returns:
        The resolved output path.

    Raises:
        RuntimeError: If pandoc is not installed.
        subprocess.CalledProcessError: If pandoc exits with an error.
    """
    pandoc = require_pandoc()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_engine = "weasyprint" if shutil.which("weasyprint") else "pdflatex"

    subprocess.run(
        [
            pandoc,
            str(markdown_path),
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
    """Build markdown, EPUB, and PDF from a Handbook.

    Args:
        handbook: Populated ``Handbook`` with post content.
        output_dir: Directory for all output files (created if missing).
        commit_hash: Git commit hash forwarded to the metadata page.
        repo_url: Repository URL forwarded to the metadata page.

    Returns:
        Dict with keys ``markdown``, ``epub``, ``pdf`` mapping to output paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_markdown_path = handbook_to_markdown(
        handbook,
        output_dir / "eahandbookcompiler.md",
        commit_hash=commit_hash,
        repo_url=repo_url,
    )
    epub_path = convert_to_epub(output_markdown_path, output_dir / "eahandbookcompiler.epub")
    pdf_path = convert_to_pdf(output_markdown_path, output_dir / "eahandbookcompiler.pdf")

    return {"markdown": output_markdown_path, "epub": epub_path, "pdf": pdf_path}
