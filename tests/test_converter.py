"""Tests for the EA Handbook converter — code-block-aware heading demotion and pandoc."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from eahandbookcompiler.converter import demote_headings, require_pandoc


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
