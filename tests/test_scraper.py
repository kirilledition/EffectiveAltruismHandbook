"""Tests for the EA Handbook scraper and converter."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ea_handbook.converter import (
    _demote_headings,
    handbook_to_markdown,
)
from ea_handbook.scraper import (
    Handbook,
    Post,
    _html_to_markdown,
    _is_ea_forum_post,
    scrape_handbook_index,
    scrape_post_content,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HANDBOOK_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <main>
    <h2>Introduction</h2>
    <ul>
      <li><a href="/posts/abc123/what-is-ea">What is Effective Altruism?</a></li>
      <li><a href="/posts/def456/doing-good-better">Doing Good Better</a></li>
    </ul>
    <h2>Global Health</h2>
    <ul>
      <li><a href="/posts/ghi789/global-health">Global Health and Development</a></li>
    </ul>
  </main>
</body>
</html>
"""

SAMPLE_POST_HTML = """\
<!DOCTYPE html>
<html>
<body>
  <div class="postBody">
    <h1>What is Effective Altruism?</h1>
    <p>Effective altruism is about doing the most good you can.</p>
    <h2>Core ideas</h2>
    <ul>
      <li>Evidence-based giving</li>
      <li>Cause prioritization</li>
    </ul>
  </div>
</body>
</html>
"""


def _make_response(html: str) -> MagicMock:
    response = MagicMock()
    response.text = html
    response.raise_for_status = MagicMock()
    response.is_redirect = False
    return response


# ---------------------------------------------------------------------------
# scraper tests
# ---------------------------------------------------------------------------


class TestIsEaForumPost:
    def test_post_url(self):
        assert _is_ea_forum_post(
            "https://forum.effectivealtruism.org/posts/abc123/title"
        )

    def test_sequence_url(self):
        assert _is_ea_forum_post(
            "https://forum.effectivealtruism.org/s/abc123"
        )

    def test_relative_post_url(self):
        assert _is_ea_forum_post("/posts/abc123/title")

    def test_external_url(self):
        assert not _is_ea_forum_post("https://example.com/posts/abc")

    def test_handbook_index_url(self):
        assert not _is_ea_forum_post("https://forum.effectivealtruism.org/handbook")


class TestScrapeHandbookIndex:
    def test_returns_posts(self):
        session = MagicMock()
        session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        posts = scrape_handbook_index(session)

        assert len(posts) == 3
        assert posts[0].title == "What is Effective Altruism?"
        assert "/posts/abc123/what-is-ea" in posts[0].url

    def test_sections_assigned(self):
        session = MagicMock()
        session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        posts = scrape_handbook_index(session)

        assert posts[0].section == "Introduction"
        assert posts[2].section == "Global Health"

    def test_no_duplicates(self):
        html = """\
        <html><body><main>
          <h2>Intro</h2>
          <ul>
            <li><a href="/posts/abc/title">Post A</a></li>
            <li><a href="/posts/abc/title">Post A</a></li>
          </ul>
        </main></body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)

        posts = scrape_handbook_index(session)
        assert len(posts) == 1

    def test_ignores_links_outside_lists(self):
        html = """\
        <html><body><main>
          <h2>Intro</h2>
          <p><a href="/posts/abc/title">Stray link</a></p>
          <ul>
            <li><a href="/posts/def/title">Real chapter</a></li>
          </ul>
        </main></body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)

        posts = scrape_handbook_index(session)
        assert len(posts) == 1
        assert posts[0].title == "Real chapter"

    def test_empty_page_returns_empty(self):
        session = MagicMock()
        session.get.return_value = _make_response("<html><body></body></html>")

        posts = scrape_handbook_index(session)
        assert posts == []


class TestScrapePostContent:
    def test_extracts_markdown(self):
        session = MagicMock()
        session.get.return_value = _make_response(SAMPLE_POST_HTML)

        post = Post(
            title="What is Effective Altruism?",
            url="https://forum.effectivealtruism.org/posts/abc123/what-is-ea",
        )
        result = scrape_post_content(post, session)

        assert "Effective altruism" in result.markdown
        assert "Core ideas" in result.markdown

    def test_fallback_on_no_body(self):
        html = "<html><body><p>Some text here.</p></body></html>"
        session = MagicMock()
        session.get.return_value = _make_response(html)

        post = Post(title="Test", url="https://forum.effectivealtruism.org/posts/x/y")
        result = scrape_post_content(post, session)

        assert result.markdown  # should still have something


# ---------------------------------------------------------------------------
# converter tests
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

class TestFetchRedirects:
    def test_fetch_no_redirect(self):
        session = MagicMock()
        response = _make_response("<html><body>content</body></html>")
        response.is_redirect = False
        session.get.return_value = response

        from ea_handbook.scraper import _fetch
        soup = _fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        session.get.assert_called_once_with("https://forum.effectivealtruism.org/post", timeout=30, allow_redirects=False)

    def test_fetch_safe_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "https://effectivealtruism.org/new-post"}

        final_response = _make_response("<html><body>content</body></html>")
        final_response.is_redirect = False

        session.get.side_effect = [redirect_response, final_response]

        from ea_handbook.scraper import _fetch
        soup = _fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        assert session.get.call_count == 2
        session.get.assert_called_with("https://effectivealtruism.org/new-post", timeout=30, allow_redirects=False)

    def test_fetch_unsafe_domain_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "https://evil.com/post"}

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch
        import pytest
        with pytest.raises(ValueError, match="Unsafe redirect domain: evil.com"):
            _fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_unsafe_scheme_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "file:///etc/passwd"}

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch
        import pytest
        with pytest.raises(ValueError, match="Unsafe redirect scheme: file"):
            _fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_too_many_redirects(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "https://forum.effectivealtruism.org/redirect"}

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch
        import pytest
        import requests
        with pytest.raises(requests.TooManyRedirects, match="Exceeded maximum redirects"):
            _fetch(session, "https://forum.effectivealtruism.org/post")
