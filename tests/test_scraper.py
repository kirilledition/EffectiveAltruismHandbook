"""Tests for the EA Handbook scraper and converter."""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from ea_handbook.converter import (
    _build_metadata_page,
    _demote_headings,
    convert_to_pdf,
    handbook_to_markdown,
)
from ea_handbook.scraper import (
    Handbook,
    Post,
    _extract_author,
    _extract_date,
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
<head>
  <meta name="author" content="William MacAskill">
  <meta property="article:published_time" content="2023-06-15T12:00:00Z">
</head>
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


class TestFetch:
    def test_fetch_http_error(self):
        import requests

        from ea_handbook.scraper import _fetch

        session = MagicMock()
        response = MagicMock()
        response.is_redirect = False
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error",
        )
        session.get.return_value = response

        with pytest.raises(requests.exceptions.HTTPError):
            _fetch(session, "https://example.com/not-found")


class TestIsEaForumPost:
    def test_post_url(self):
        assert _is_ea_forum_post(
            "https://forum.effectivealtruism.org/posts/abc123/title",
        )

    def test_sequence_url(self):
        assert _is_ea_forum_post("https://forum.effectivealtruism.org/s/abc123")

    def test_relative_post_url(self):
        assert _is_ea_forum_post("/posts/abc123/title")

    def test_external_url(self):
        assert not _is_ea_forum_post("https://example.com/posts/abc")

    def test_handbook_index_url(self):
        assert not _is_ea_forum_post("https://forum.effectivealtruism.org/handbook")

    def test_invalid_scheme(self):
        assert not _is_ea_forum_post("javascript:alert(1)")
        assert not _is_ea_forum_post("file:///etc/passwd")
        assert not _is_ea_forum_post("data:text/html,<script>alert(1)</script>")


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

    def test_extracts_author_and_date(self):
        session = MagicMock()
        session.get.return_value = _make_response(SAMPLE_POST_HTML)

        post = Post(
            title="What is Effective Altruism?",
            url="https://forum.effectivealtruism.org/posts/abc123/what-is-ea",
        )
        result = scrape_post_content(post, session)

        assert result.author == "William MacAskill"
        assert result.posted_date == "2023-06-15"


class TestExtractAuthor:
    def test_json_ld_author(self):
        html = '<html><head><script type="application/ld+json">{"author": {"name": "Peter Singer"}}</script></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert _extract_author(soup) == "Peter Singer"

    def test_meta_author(self):
        html = '<html><head><meta name="author" content="Toby Ord"></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert _extract_author(soup) == "Toby Ord"

    def test_no_author_returns_empty(self):
        html = "<html><body><p>Hello</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _extract_author(soup) == ""


class TestExtractDate:
    def test_meta_date(self):
        html = '<html><head><meta property="article:published_time" content="2022-03-10T08:00:00Z"></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert _extract_date(soup) == "2022-03-10"

    def test_time_element(self):
        html = '<html><body><time datetime="2021-01-05T10:00:00Z">Jan 5</time></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert _extract_date(soup) == "2021-01-05"

    def test_no_date_returns_empty(self):
        html = "<html><body><p>Hello</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _extract_date(soup) == ""


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
                ),
            ],
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
            ],
        )
        out = tmp_path / "output.md"
        handbook_to_markdown(handbook, out)
        content = out.read_text()

        assert content.count("# Sec") == 1

    def test_creates_parent_dirs(self, tmp_path):
        handbook = Handbook(posts=[Post(title="T", url="u", section="S", markdown="m")])
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
                ),
            ],
        )
        out = tmp_path / "output.md"
        handbook_to_markdown(handbook, out)
        content = out.read_text()

        assert "https://forum.effectivealtruism.org/posts/x/y" in content

    def test_includes_metadata_page(self, tmp_path):
        handbook = Handbook(
            posts=[
                Post(
                    title="Post",
                    url="u",
                    section="S",
                    author="Alice",
                    posted_date="2023-01-15",
                    markdown="text",
                ),
            ],
        )
        out = tmp_path / "output.md"
        handbook_to_markdown(handbook, out)
        content = out.read_text()

        assert "# About This Book" in content
        assert "Alice" in content
        assert "2023-01-15" in content


class TestBuildMetadataPage:
    def test_authors_sorted_two_columns(self):
        handbook = Handbook(
            posts=[
                Post(title="A", url="u", author="Zara", posted_date="2023-01-01", markdown="m"),
                Post(title="B", url="u", author="Alice", posted_date="2023-06-01", markdown="m"),
                Post(title="C", url="u", author="Bob", posted_date="2023-03-15", markdown="m"),
            ],
        )
        page = _build_metadata_page(handbook)

        assert "# About This Book" in page
        assert "2023-01-01" in page
        assert "2023-06-01" in page
        # Authors in alphabetical order
        alice_pos = page.index("Alice")
        bob_pos = page.index("Bob")
        zara_pos = page.index("Zara")
        assert alice_pos < bob_pos < zara_pos
        # Table format
        assert "|" in page

    def test_no_authors_no_dates(self):
        handbook = Handbook(
            posts=[Post(title="A", url="u", markdown="m")],
        )
        page = _build_metadata_page(handbook)

        assert "# About This Book" in page
        assert "unknown" in page


class TestHtmlToMarkdown:
    def test_preserves_links(self):

        html = '<div><p>Read <a href="https://example.com">this study</a>.</p></div>'
        element = BeautifulSoup(html, "lxml").find("div")
        md = _html_to_markdown(element)

        assert "https://example.com" in md
        assert "this study" in md

    def test_removes_comment_sections(self):
        html = (
            "<div>"
            "<p>Main content.</p>"
            '<div class="CommentsSection"><p>A user comment.</p></div>'
            "</div>"
        )
        element = BeautifulSoup(html, "lxml").find("div")
        md = _html_to_markdown(element)

        assert "Main content" in md
        assert "user comment" not in md


class TestConvertToEpub:
    @patch("ea_handbook.converter.subprocess.run")
    @patch("ea_handbook.converter._require_pandoc")
    def test_convert_to_epub(self, mock_require_pandoc, mock_subprocess_run, tmp_path):
        from ea_handbook.converter import convert_to_epub

        mock_require_pandoc.return_value = "/usr/bin/pandoc"

        md_path = tmp_path / "input.md"
        out_path = tmp_path / "output.epub"

        result = convert_to_epub(md_path, out_path)

        assert result == out_path
        mock_require_pandoc.assert_called_once()
        mock_subprocess_run.assert_called_once_with(
            [
                "/usr/bin/pandoc",
                str(md_path),
                "--sandbox",
                "--from=markdown",
                "--to=epub3",
                f"--output={out_path}",
                "--toc",
                "--toc-depth=2",
                "--epub-chapter-level=2",
            ],
            check=True,
        )
        assert out_path.parent.exists()


class TestConvertToPdf:
    @patch("ea_handbook.converter.subprocess.run")
    @patch("ea_handbook.converter.shutil.which")
    def test_convert_to_pdf_sandbox(self, mock_which, mock_run, tmp_path):
        # Mocking which: first call is for pandoc, second is for weasyprint
        mock_which.side_effect = ["/usr/bin/pandoc", "/usr/bin/weasyprint"]
        md_path = tmp_path / "test.md"
        out_path = tmp_path / "test.pdf"

        convert_to_pdf(md_path, out_path)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--sandbox" in args


class TestFetchRedirects:
    def test_fetch_no_redirect(self):
        session = MagicMock()
        response = _make_response("<html><body>content</body></html>")
        response.is_redirect = False
        session.get.return_value = response

        from ea_handbook.scraper import _fetch

        soup = _fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        session.get.assert_called_once_with(
            "https://forum.effectivealtruism.org/post",
            timeout=30,
            allow_redirects=False,
        )

    def test_fetch_safe_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {
            "Location": "https://effectivealtruism.org/new-post",
        }

        final_response = _make_response("<html><body>content</body></html>")
        final_response.is_redirect = False

        session.get.side_effect = [redirect_response, final_response]

        from ea_handbook.scraper import _fetch

        soup = _fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        assert session.get.call_count == 2

    def test_fetch_unsafe_domain_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "https://evil.com/post"}

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch

        with pytest.raises(ValueError, match="Unsafe redirect domain: evil.com"):
            _fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_unsafe_scheme_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "file:///etc/passwd"}

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch

        with pytest.raises(ValueError, match="Unsafe redirect scheme: file"):
            _fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_too_many_redirects(self):
        import requests as req

        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {
            "Location": "https://forum.effectivealtruism.org/redirect",
        }

        session.get.return_value = redirect_response

        from ea_handbook.scraper import _fetch

        with pytest.raises(
            req.TooManyRedirects, match="Exceeded maximum redirects",
        ):
            _fetch(session, "https://forum.effectivealtruism.org/post")
