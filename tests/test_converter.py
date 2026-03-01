"""Tests for the EA Handbook converter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ea_handbook.converter import (
    _demote_headings,
    handbook_to_markdown,
    _require_pandoc,
)
from ea_handbook.scraper import Handbook, Post, _html_to_markdown

# ---------------------------------------------------------------------------
# converter tests
# ---------------------------------------------------------------------------

class TestRequirePandoc:
    @patch("shutil.which")
    def test_success(self, mock_which):
        mock_which.return_value = "/usr/bin/pandoc"
        result = _require_pandoc()
        assert result == "/usr/bin/pandoc"
        mock_which.assert_called_once_with("pandoc")

    @patch("shutil.which")
    def test_missing_raises_runtime_error(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(RuntimeError) as exc_info:
            _require_pandoc()
        assert "pandoc is not installed" in str(exc_info.value)
        mock_which.assert_called_once_with("pandoc")
# ---------------------------------------------------------------------------


class TestDemoteHeadings:
    def test_demotes_h1(self):
        result = _demote_headings("# Heading", levels=2)
        assert result == "### Heading"

    def test_demotes_h2(self):
        result = _demote_headings("## Subheading", levels=2)
        assert result == "#### Subheading"

    def test_non_heading_unchanged(self):
        result = _demote_headings("Normal paragraph", levels=2)
        assert result == "Normal paragraph"

    def test_multiline(self):
        text = "# Title\nSome text.\n## Sub"
        result = _demote_headings(text, levels=1)
        assert result == "## Title\nSome text.\n### Sub"

    def test_hash_without_space_unchanged(self):
        result = _demote_headings("#comment", levels=2)
        assert result == "#comment"

    def test_shebang_unchanged(self):
        result = _demote_headings("#!/bin/bash", levels=2)
        assert result == "#!/bin/bash"

    def test_code_comment_without_space_unchanged(self):
        text = "```python\n#!no heading\nprint('hello')\n```"
        result = _demote_headings(text, levels=2)
        assert "#!no heading" in result


class TestHandbookToMarkdown:
    def test_writes_file(self, tmp_path):
        handbook = Handbook(
            posts=[
                Post(
                    title="Post One",
                    url="https://example.com",
                    section="Intro",
                    markdown="Hello world.",
                )
            ]
        )
        out = tmp_path / "output.md"
        result = handbook_to_markdown(handbook, out)

        assert result == out
        content = out.read_text()
        assert "# Intro" in content
        assert "## Post One" in content
        assert "Hello world." in content

    def test_section_headings_not_repeated(self, tmp_path):
        handbook = Handbook(
            posts=[
                Post(title="A", url="u1", section="Sec", markdown="text"),
                Post(title="B", url="u2", section="Sec", markdown="text"),
            ]
        )
        out = tmp_path / "output.md"
        handbook_to_markdown(handbook, out)
        content = out.read_text()

        assert content.count("# Sec") == 1

    def test_creates_parent_dirs(self, tmp_path):
        handbook = Handbook(
            posts=[Post(title="T", url="u", section="S", markdown="m")]
        )
        out = tmp_path / "nested" / "dir" / "output.md"
        handbook_to_markdown(handbook, out)

        assert out.exists()

    def test_missing_markdown_uses_url(self, tmp_path):
        handbook = Handbook(
            posts=[
                Post(
                    title="Empty Post",
                    url="https://forum.effectivealtruism.org/posts/x/y",
                    section="S",
                    markdown="",
                )
            ]
        )
        out = tmp_path / "output.md"
        handbook_to_markdown(handbook, out)
        content = out.read_text()

        assert "https://forum.effectivealtruism.org/posts/x/y" in content


class TestHtmlToMarkdown:
    def test_preserves_links(self):
        from bs4 import BeautifulSoup

        html = '<div><p>Read <a href="https://example.com">this study</a>.</p></div>'
        element = BeautifulSoup(html, "lxml").find("div")
        md = _html_to_markdown(element)

        assert "https://example.com" in md
        assert "this study" in md

    def test_removes_comment_sections(self):
        from bs4 import BeautifulSoup

        html = (
            '<div>'
            '<p>Main content.</p>'
            '<div class="CommentsSection"><p>A user comment.</p></div>'
            '</div>'
        )
        element = BeautifulSoup(html, "lxml").find("div")
        md = _html_to_markdown(element)

        assert "Main content" in md
        assert "user comment" not in md
