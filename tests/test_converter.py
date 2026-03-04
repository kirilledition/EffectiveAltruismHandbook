"""Tests for the EA Handbook converter — code-block-aware heading demotion and pandoc."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from eahandbookcompiler.converter import PDF_CSS, demote_headings, require_pandoc


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
