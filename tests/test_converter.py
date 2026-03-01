from ea_handbook.converter import _demote_headings

def test_demote_headings_basic():
    text = "# Heading 1\n## Heading 2\nSome text."
    expected = "### Heading 1\n#### Heading 2\nSome text."
    assert _demote_headings(text, levels=2) == expected

def test_demote_headings_ignores_code_blocks():
    text = """# Heading 1
Some text.
```python
# A python comment
def foo():
    pass
```
## Heading 2"""
    expected = """### Heading 1
Some text.
```python
# A python comment
def foo():
    pass
```
#### Heading 2"""
    assert _demote_headings(text, levels=2) == expected

def test_demote_headings_ignores_tilde_code_blocks():
    text = """# Heading 1
Some text.
~~~bash
# A bash comment
echo "hello"
~~~
## Heading 2"""
    expected = """### Heading 1
Some text.
~~~bash
# A bash comment
echo "hello"
~~~
#### Heading 2"""
    assert _demote_headings(text, levels=2) == expected

def test_demote_headings_ignores_indented_code_blocks():
    text = """# Heading 1
Some text.

    # Indented code block
    echo "hello"

## Heading 2"""
    expected = """### Heading 1
Some text.

    # Indented code block
    echo "hello"

#### Heading 2"""
    assert _demote_headings(text, levels=2) == expected
