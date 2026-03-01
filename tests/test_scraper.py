"""Tests for the EA Handbook scraper."""

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
