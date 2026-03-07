"""Tests for the EA Handbook converter — code-block-aware heading demotion and pandoc."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from eahandbookcompiler.converter import PDF_CSS, demote_headings, require_pandoc
from eahandbookcompiler.scraper import Handbook, Post


class TestDemoteHeadingsCodeBlocks:
    def test_ignores_backtick_code_blocks(self):
        text = """\
# Heading 1
Some text.
```python
# A python comment
def foo():
    pass
```
## Heading 2"""
        expected = """\
### Heading 1
Some text.
```python
# A python comment
def foo():
    pass
```
#### Heading 2"""
        assert demote_headings(text, levels=2) == expected

    def test_ignores_tilde_code_blocks(self):
        text = """\
# Heading 1
Some text.
~~~bash
# A bash comment
echo "hello"
~~~
## Heading 2"""
        expected = """\
### Heading 1
Some text.
~~~bash
# A bash comment
echo "hello"
~~~
#### Heading 2"""
        assert demote_headings(text, levels=2) == expected

    def test_ignores_indented_code_blocks(self):
        text = """\
# Heading 1
Some text.

    # Indented code block
    echo "hello"

## Heading 2"""
        expected = """\
### Heading 1
Some text.

    # Indented code block
    echo "hello"

#### Heading 2"""
        assert demote_headings(text, levels=2) == expected


class TestRequirePandocErrorPath:
    @patch("shutil.which")
    def test_missing_raises_runtime_error(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(RuntimeError, match="pandoc is not installed"):
            require_pandoc()
        mock_which.assert_called_once_with("pandoc")


class TestPdfCss:
    def test_contains_liberation_sans(self):
        assert '"Liberation Sans"' in PDF_CSS

    def test_contains_small_margins(self):
        assert "margin: 1.0cm" in PDF_CSS

    def test_contains_small_font_size(self):
        assert "font-size: 10pt" in PDF_CSS

    def test_contains_img_max_width(self):
        assert "max-width: 100%" in PDF_CSS

    def test_contains_img_height_auto(self):
        assert "height: auto" in PDF_CSS

    def test_contains_h1_page_break(self):
        assert "page-break-before: always" in PDF_CSS


class TestDemoteHeadingsCap:
    def test_caps_at_h6(self):
        result = demote_headings("##### Heading", levels=2)
        assert result == "###### Heading"

    def test_h6_stays_at_h6(self):
        result = demote_headings("###### Heading", levels=2)
        assert result == "###### Heading"


class TestBylineVariants:
    def test_author_only_byline(self, tmp_path):
        from eahandbookcompiler.converter import handbook_to_markdown

        handbook = Handbook(
            posts=[Post(title="P", url="u", section="S", author="Alice", posted_date="", markdown="text")],
        )
        output = tmp_path / "out.md"
        handbook_to_markdown(handbook, output)
        content = output.read_text()
        assert "*By Alice*" in content

    def test_date_only_byline(self, tmp_path):
        from eahandbookcompiler.converter import handbook_to_markdown

        handbook = Handbook(
            posts=[Post(title="P", url="u", section="S", author="", posted_date="2024-01-01", markdown="text")],
        )
        output = tmp_path / "out.md"
        handbook_to_markdown(handbook, output)
        content = output.read_text()
        assert "*2024-01-01*" in content


class TestBuildAll:
    @patch("eahandbookcompiler.converter.convert_to_pdf")
    @patch("eahandbookcompiler.converter.convert_to_epub")
    def test_build_all_returns_paths(self, mock_epub, mock_pdf, tmp_path):
        from eahandbookcompiler.converter import build_all

        mock_epub.return_value = tmp_path / "eahandbookcompiler.epub"
        mock_pdf.return_value = tmp_path / "eahandbookcompiler.pdf"

        handbook = Handbook(
            posts=[Post(title="T", url="u", section="S", markdown="m")],
        )
        result = build_all(handbook, tmp_path, commit_hash="abc", repo_url="https://example.com")

        assert "markdown" in result
        assert "epub" in result
        assert "pdf" in result
        assert result["markdown"].exists()
        mock_epub.assert_called_once()
        mock_pdf.assert_called_once()


class TestPandocSandbox:
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_epub_uses_sandbox(self, mock_which, mock_run, tmp_path):
        from eahandbookcompiler.converter import convert_to_epub

        mock_which.return_value = "pandoc"
        convert_to_epub(tmp_path / "in.md", tmp_path / "out.epub")

        args, kwargs = mock_run.call_args
        cmd_list = args[0]
        assert "--sandbox" in cmd_list
        assert kwargs["check"] is True

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_pdf_uses_sandbox(self, mock_which, mock_run, tmp_path):
        from eahandbookcompiler.converter import convert_to_pdf

        mock_which.return_value = "pandoc"
        convert_to_pdf(tmp_path / "in.md", tmp_path / "out.pdf")

        args, kwargs = mock_run.call_args
        cmd_list = args[0]
        assert "--sandbox" in cmd_list
        assert kwargs["check"] is True
