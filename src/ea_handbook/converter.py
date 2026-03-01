"""Convert a Handbook to markdown, epub, and pdf via pandoc."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ea_handbook.scraper import Handbook

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


def handbook_to_markdown(handbook: Handbook, output_path: Path) -> Path:
    """
    Write the handbook to a single markdown file.

    Returns the path of the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [PANDOC_METADATA]
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
    return re.sub(r"^(?=#+ )", "#" * levels, text, flags=re.MULTILINE)


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


def build_all(handbook: Handbook, output_dir: Path) -> dict[str, Path]:
    """
    Build markdown, epub, and pdf from a Handbook.

    Returns a dict with keys 'markdown', 'epub', 'pdf'.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = handbook_to_markdown(handbook, output_dir / "ea-handbook.md")
    epub_path = convert_to_epub(md_path, output_dir / "ea-handbook.epub")
    pdf_path = convert_to_pdf(md_path, output_dir / "ea-handbook.pdf")

    return {"markdown": md_path, "epub": epub_path, "pdf": pdf_path}
