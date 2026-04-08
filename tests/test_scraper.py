"""Tests for the EA Handbook scraper and converter."""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from eahandbookcompiler.converter import (
    build_metadata_page,
    convert_to_pdf,
    demote_headings,
    handbook_to_markdown,
)
from eahandbookcompiler.scraper import (
    Handbook,
    Post,
    extract_author,
    extract_date,
    html_to_markdown,
    is_ea_forum_post,
    scrape_all,
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
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=None)
    response.text = html
    response.raise_for_status = MagicMock()
    response.is_redirect = False
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.encoding = "utf-8"
    response.iter_content.return_value = [html.encode("utf-8")]
    return response


# ---------------------------------------------------------------------------
# scraper tests
# ---------------------------------------------------------------------------


class TestFetch:
    def test_fetch_http_error(self):
        import requests

        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = MagicMock()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)
        response.is_redirect = False
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error",
        )
        session.get.return_value = response

        with pytest.raises(requests.exceptions.HTTPError):
            fetch(session, "https://effectivealtruism.org/not-found")


class TestIsEaForumPost:
    def test_post_url(self):
        assert is_ea_forum_post(
            "https://forum.effectivealtruism.org/posts/abc123/title",
        )

    def test_sequence_url(self):
        assert is_ea_forum_post("https://forum.effectivealtruism.org/s/abc123")

    def test_relative_post_url(self):
        assert is_ea_forum_post("/posts/abc123/title")

    def test_external_url(self):
        assert not is_ea_forum_post("https://example.com/posts/abc")

    def test_handbook_index_url(self):
        assert not is_ea_forum_post("https://forum.effectivealtruism.org/handbook")

    def test_invalid_scheme(self):
        assert not is_ea_forum_post("javascript:alert(1)")
        assert not is_ea_forum_post("file:///etc/passwd")
        assert not is_ea_forum_post("data:text/html,<script>alert(1)</script>")

    def test_path_traversal(self):
        assert not is_ea_forum_post("https://forum.effectivealtruism.org/posts/../../../../etc/passwd")
        assert not is_ea_forum_post("/posts/abc/../../../../../../etc/passwd")


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


class TestScrapeAllConcurrent:
    @patch("eahandbookcompiler.scraper.make_session")
    def test_concurrent_populates_all_posts(self, mock_make_session):
        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        handbook = scrape_all(session=index_session, delay=0, max_workers=2)

        assert len(handbook.posts) == 3
        for post in handbook.posts:
            assert post.markdown
            assert post.author == "William MacAskill"

    def test_sequential_populates_all_posts(self):
        session = MagicMock()
        index_response = _make_response(SAMPLE_HANDBOOK_HTML)
        post_response = _make_response(SAMPLE_POST_HTML)
        session.get.side_effect = [index_response, post_response, post_response, post_response]

        handbook = scrape_all(session=session, delay=0, max_workers=1)

        assert len(handbook.posts) == 3
        for post in handbook.posts:
            assert post.markdown

    @patch("eahandbookcompiler.scraper.make_session")
    def test_concurrent_with_cache(self, mock_make_session, tmp_path):
        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        handbook = scrape_all(session=index_session, delay=0, max_workers=2, cache_dir=tmp_path)

        assert len(handbook.posts) == 3
        cache_files = list(tmp_path.glob("*.json"))
        assert len(cache_files) == 3

    @patch("eahandbookcompiler.scraper.make_session")
    def test_concurrent_propagates_errors(self, mock_make_session):
        import requests as req

        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        error_response = MagicMock()
        error_response.__enter__ = MagicMock(return_value=error_response)
        error_response.__exit__ = MagicMock(return_value=None)
        error_response.is_redirect = False
        error_response.raise_for_status.side_effect = req.exceptions.HTTPError("500 Server Error")

        error_session = MagicMock()
        error_session.get.return_value = error_response
        mock_make_session.return_value = error_session

        with pytest.raises(req.exceptions.HTTPError):
            scrape_all(session=index_session, delay=0, max_workers=2)


class TestExtractAuthor:
    def test_json_ld_author(self):
        html = (
            '<html><head><script type="application/ld+json">'
            '{"author": {"name": "Peter Singer"}}'
            "</script></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "Peter Singer"

    def test_meta_author(self):
        html = '<html><head><meta name="author" content="Toby Ord"></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "Toby Ord"

    def test_byline_div_not_matched(self):
        """A byline div wrapping author, date, and read time must not be matched."""
        html = (
            "<html><body>"
            '<div class="PostsPagePostHeader-byline">'
            '<a class="UsersName-root">Jane Smith</a>'
            "<span>May 10, 2024</span>"
            "<span>5 min read</span>"
            "</div>"
            "</body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "Jane Smith"

    def test_author_in_anchor_tag(self):
        html = '<html><body><a class="author-name">Alice</a></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "Alice"

    def test_author_in_span_tag(self):
        html = '<html><body><span class="author">Bob</span></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "Bob"

    def test_author_div_ignored(self):
        """A div with class 'author' should not be matched."""
        html = '<html><body><div class="author">Eve</div></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == ""

    def test_no_author_returns_empty(self):
        html = "<html><body><p>Hello</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == ""


class TestExtractDate:
    def test_meta_date(self):
        html = (
            '<html><head><meta property="article:published_time"'
            ' content="2022-03-10T08:00:00Z"></head><body></body></html>'
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2022-03-10"

    def test_time_element(self):
        html = '<html><body><time datetime="2021-01-05T10:00:00Z">Jan 5</time></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2021-01-05"

    def test_no_date_returns_empty(self):
        html = "<html><body><p>Hello</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == ""


# ---------------------------------------------------------------------------
# converter tests
# ---------------------------------------------------------------------------


class TestDemoteHeadings:
    def test_demotes_h1(self):
        result = demote_headings("# Heading", levels=2)
        assert result == "### Heading"

    def test_demotes_h2(self):
        result = demote_headings("## Subheading", levels=2)
        assert result == "#### Subheading"

    def test_non_heading_unchanged(self):
        result = demote_headings("Normal paragraph", levels=2)
        assert result == "Normal paragraph"

    def test_multiline(self):
        text = "# Title\nSome text.\n## Sub"
        result = demote_headings(text, levels=1)
        assert result == "## Title\nSome text.\n### Sub"

    def test_hash_without_space_unchanged(self):
        result = demote_headings("#comment", levels=2)
        assert result == "#comment"

    def test_shebang_unchanged(self):
        result = demote_headings("#!/bin/bash", levels=2)
        assert result == "#!/bin/bash"

    def test_code_comment_without_space_unchanged(self):
        text = "```python\n#!no heading\nprint('hello')\n```"
        result = demote_headings(text, levels=2)
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
        output_path = tmp_path / "output.markdown"
        result = handbook_to_markdown(handbook, output_path)

        assert result == output_path
        content = output_path.read_text()
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
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        assert content.count("# Sec") == 1

    def test_creates_parent_dirs(self, tmp_path):
        handbook = Handbook(posts=[Post(title="T", url="u", section="S", markdown="m")])
        output_path = tmp_path / "nested" / "dir" / "output.markdown"
        handbook_to_markdown(handbook, output_path)

        assert output_path.exists()

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
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

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
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        assert "# About This Book" in content
        assert "Alice" in content
        assert "2023-01-15" in content

    def test_includes_title_page(self, tmp_path):
        handbook = Handbook(
            posts=[Post(title="T", url="u", section="S", markdown="m")],
        )
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        assert "# The Effective Altruism Handbook" in content

    def test_includes_toc_directive(self, tmp_path):
        handbook = Handbook(
            posts=[Post(title="T", url="u", section="S", markdown="m")],
        )
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        assert "\\tableofcontents" in content

    def test_about_before_toc(self, tmp_path):
        handbook = Handbook(
            posts=[Post(title="T", url="u", section="S", author="A", posted_date="2023-01-01", markdown="m")],
        )
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        about_pos = content.index("# About This Book")
        toc_pos = content.index("\\tableofcontents")
        assert about_pos < toc_pos

    def test_includes_author_byline(self, tmp_path):
        handbook = Handbook(
            posts=[
                Post(
                    title="My Post",
                    url="u",
                    section="S",
                    author="Bob",
                    posted_date="2024-05-10",
                    markdown="content",
                ),
            ],
        )
        output_path = tmp_path / "output.markdown"
        handbook_to_markdown(handbook, output_path)
        content = output_path.read_text()

        assert "*By Bob on 2024-05-10*" in content


class TestBuildMetadataPage:
    def test_authors_sorted_comma_separated(self):
        handbook = Handbook(
            posts=[
                Post(
                    title="A",
                    url="u",
                    author="Zara",
                    posted_date="2023-01-01",
                    markdown="m",
                ),
                Post(
                    title="B",
                    url="u",
                    author="Alice",
                    posted_date="2023-06-01",
                    markdown="m",
                ),
                Post(
                    title="C",
                    url="u",
                    author="Bob",
                    posted_date="2023-03-15",
                    markdown="m",
                ),
            ],
        )
        page = build_metadata_page(handbook)

        assert "# About This Book" in page
        assert "2023-01-01" in page
        assert "2023-06-01" in page
        # Authors in alphabetical order, comma-separated
        assert "Alice, Bob, Zara" in page

    def test_no_authors_no_dates(self):
        handbook = Handbook(
            posts=[Post(title="A", url="u", markdown="m")],
        )
        page = build_metadata_page(handbook)

        assert "# About This Book" in page
        assert "unknown" in page


class TestHtmlToMarkdown:
    def test_sanitizes_href_and_src_attributes(self):
        html = (
            '<div><a href="javascript:alert(1)">Click me</a>'
            '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" /></div>'
        )
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "javascript:alert(1)" not in markdown
        assert "data:image/gif;base64" not in markdown
        assert "Click me" in markdown

    def test_preserves_links(self):

        html = '<div><p>Read <a href="https://example.com">this study</a>.</p></div>'
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "https://example.com" in markdown
        assert "this study" in markdown

    def test_removes_comment_sections(self):
        html = '<div><p>Main content.</p><div class="CommentsSection"><p>A user comment.</p></div></div>'
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "Main content" in markdown
        assert "user comment" not in markdown


class TestConvertToEpub:
    @patch("eahandbookcompiler.converter.subprocess.run")
    @patch("eahandbookcompiler.converter.require_pandoc")
    def test_convert_to_epub(self, mock_require_pandoc, mock_subprocess_run, tmp_path):
        from eahandbookcompiler.converter import convert_to_epub

        mock_require_pandoc.return_value = "/usr/bin/pandoc"

        markdown_path = tmp_path / "input.markdown"
        test_output_path = tmp_path / "output.epub"

        result = convert_to_epub(markdown_path, test_output_path)

        assert result == test_output_path
        mock_require_pandoc.assert_called_once()
        mock_subprocess_run.assert_called_once_with(
            [
                "/usr/bin/pandoc",
                str(markdown_path),
                "--from=markdown",
                "--to=epub3",
                "--sandbox",
                f"--output={test_output_path}",
                "--toc-depth=2",
                "--split-level=2",
                f"--css={test_output_path.parent / 'epub.css'}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert test_output_path.parent.exists()


class TestConvertToPdf:
    @patch("eahandbookcompiler.converter.subprocess.run")
    @patch("eahandbookcompiler.converter.shutil.which")
    def test_convert_to_pdf_command(self, mock_which, mock_run, tmp_path):
        # Mocking which: first call is for pandoc, second is for weasyprint
        mock_which.side_effect = ["/usr/bin/pandoc", "/usr/bin/weasyprint"]
        markdown_path = tmp_path / "test.markdown"
        test_output_path = tmp_path / "test.pdf"

        convert_to_pdf(markdown_path, test_output_path)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--sandbox" in args
        assert f"--css={test_output_path.parent / 'pdf.css'}" in args


class TestFetchRedirects:
    def test_fetch_no_redirect(self):
        session = MagicMock()
        response = _make_response("<html><body>content</body></html>")
        response.is_redirect = False
        session.get.return_value = response

        from eahandbookcompiler.scraper import fetch

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        session.get.assert_called_once_with(
            "https://forum.effectivealtruism.org/post",
            timeout=30,
            allow_redirects=False,
            stream=True,
        )

    def test_fetch_safe_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.encoding = "utf-8"
        redirect_response.iter_content.return_value = []
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = "https://effectivealtruism.org/new-post"

        final_response = _make_response("<html><body>content</body></html>")
        final_response.is_redirect = False

        session.get.side_effect = [redirect_response, final_response]

        from eahandbookcompiler.scraper import fetch

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "content"
        assert session.get.call_count == 2

    def test_fetch_unsafe_domain_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = "https://evil.com/post"

        session.get.return_value = redirect_response

        from eahandbookcompiler.scraper import fetch

        with pytest.raises(ValueError, match=r"Unsafe URL domain: evil\.com"):
            fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_unsafe_scheme_redirect(self):
        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = "file:///etc/passwd"

        session.get.return_value = redirect_response

        from eahandbookcompiler.scraper import fetch

        with pytest.raises(ValueError, match="Unsafe URL scheme: file"):
            fetch(session, "https://forum.effectivealtruism.org/post")

    def test_fetch_too_many_redirects(self):
        import requests as req

        session = MagicMock()

        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = "https://forum.effectivealtruism.org/redirect"

        session.get.return_value = redirect_response

        from eahandbookcompiler.scraper import fetch

        with pytest.raises(
            req.TooManyRedirects,
            match="Exceeded maximum redirects",
        ):
            fetch(session, "https://forum.effectivealtruism.org/post")


class TestCcLicenseFilter:
    def test_removes_creative_commons_footer(self):
        html = "<div><p>Main content.</p><p>Licensed under Creative Commons Attribution 4.0.</p></div>"
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "Main content" in markdown
        assert "Creative Commons" not in markdown

    def test_removes_cc_by_footer(self):
        html = "<div><p>Main content.</p><p>CC BY 4.0 International License</p></div>"
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "Main content" in markdown
        assert "CC BY" not in markdown

    def test_preserves_non_cc_license(self):
        html = "<div><p>Main content.</p><p>Licensed under the MIT License.</p></div>"
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)

        assert "Main content" in markdown
        assert "MIT License" in markdown


class TestCleanAuthorName:
    def test_strips_html_tags(self):
        html = '<html><head><meta name="author" content="<b>John Doe</b>"></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "John Doe"

    def test_collapses_whitespace(self):
        html = '<html><head><meta name="author" content="  John   Doe  "></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author(soup) == "John Doe"


class TestMakeSession:
    def test_returns_session_with_user_agent(self):
        from eahandbookcompiler.scraper import make_session

        session = make_session()
        assert "EA-Handbook-Bot" in session.headers["User-Agent"]


class TestFetchRedirectMissingLocation:
    def test_redirect_without_location_returns_fallback(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = None
        redirect_response.text = "<html><body>fallback</body></html>"
        redirect_response.raise_for_status = MagicMock()

        redirect_response.encoding = "utf-8"
        redirect_response.iter_content.return_value = [b"<html><body>fallback</body></html>"]

        session.get.return_value = redirect_response

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup is not None


class TestHtmlToMarkdownStripping:
    def test_removes_nav_and_footer(self):
        html = "<div><nav>Menu</nav><p>Content</p><footer>Footer</footer></div>"
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)
        assert "Content" in markdown
        assert "Menu" not in markdown
        assert "Footer" not in markdown

    def test_removes_script_style_noscript(self):
        html = "<div><script>alert(1)</script><style>.x{}</style><noscript>No JS</noscript><p>Text</p></div>"
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)
        assert "Text" in markdown
        assert "alert" not in markdown
        assert ".x{}" not in markdown
        assert "No JS" not in markdown

    def test_removes_aria_hidden(self):
        html = '<div><p>Visible</p><span aria-hidden="true">Hidden</span></div>'
        element = BeautifulSoup(html, "lxml").find("div")
        assert element is not None
        markdown = html_to_markdown(element)
        assert "Visible" in markdown
        assert "Hidden" not in markdown


class TestExtractAuthorJsonLdEdgeCases:
    def test_invalid_json_skipped(self):
        from eahandbookcompiler.scraper import extract_author_json_ld

        html = '<html><head><script type="application/ld+json">not valid json</script></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author_json_ld(soup) == ""

    def test_non_dict_data_skipped(self):
        from eahandbookcompiler.scraper import extract_author_json_ld

        html = '<html><head><script type="application/ld+json">[1, 2, 3]</script></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_author_json_ld(soup) == ""

    def test_string_author(self):
        from eahandbookcompiler.scraper import extract_author_json_ld

        html = (
            '<html><head><script type="application/ld+json">'
            '{"author": "Jane Author"}'
            "</script></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_author_json_ld(soup) == "Jane Author"

    def test_dict_author_without_name(self):
        from eahandbookcompiler.scraper import extract_author_json_ld

        html = (
            '<html><head><script type="application/ld+json">'
            '{"author": {"url": "https://example.com"}}'
            "</script></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_author_json_ld(soup) == ""


class TestExtractDateJsonLd:
    def test_json_ld_date_published(self):
        html = (
            '<html><head><script type="application/ld+json">'
            '{"datePublished": "2023-05-20T10:00:00Z"}'
            "</script></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2023-05-20"

    def test_json_ld_date_created(self):
        html = (
            '<html><head><script type="application/ld+json">'
            '{"dateCreated": "2022-11-15T08:30:00Z"}'
            "</script></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2022-11-15"

    def test_json_ld_invalid_json_skipped(self):
        html = (
            '<html><head><script type="application/ld+json">bad json</script></head>'
            '<body><time datetime="2021-01-01T00:00:00Z">Jan 1</time></body></html>'
        )
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2021-01-01"

    def test_meta_date_published(self):
        html = '<html><head><meta property="datePublished" content="2024-07-01T00:00:00Z"></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_date(soup) == "2024-07-01"


class TestFindLargestContentDivision:
    def test_returns_largest_div(self):
        from eahandbookcompiler.scraper import find_largest_content_division

        html = "<html><body><div>Short</div><div>This is a much longer text content area</div></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = find_largest_content_division(soup)
        assert result is not None
        assert "much longer" in result.get_text()

    def test_returns_none_for_no_divs(self):
        from eahandbookcompiler.scraper import find_largest_content_division

        html = "<html><body><p>No divs here</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = find_largest_content_division(soup)
        # lxml wraps content in html/body tags. Since the function specifically
        # searches for div elements and none exist in the original HTML, it returns None.
        assert result is None


class TestExtractFromReactStructure:
    def test_extracts_posts_from_react_structure(self):
        from eahandbookcompiler.scraper import _extract_from_react_structure

        html = """
        <div>
            <div class="LargeSequencesItem-columns">
                <div class="LargeSequencesItem-titleAndAuthor">
                    <a href="/s/intro">Introduction Section</a>
                </div>
                <div class="LargeSequencesItem-right">
                    <a href="/posts/abc/first-post">First Post</a>
                    <a href="/posts/def/second-post">Second Post</a>
                </div>
            </div>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = _extract_from_react_structure(content)
        assert len(posts) == 2
        assert posts[0].title == "First Post"
        assert posts[0].section == "Introduction Section"

    def test_empty_react_structure(self):
        from eahandbookcompiler.scraper import _extract_from_react_structure

        html = "<div><p>No react items</p></div>"
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = _extract_from_react_structure(content)
        assert posts == []


class TestExtractFromHeadingStructure:
    def test_extracts_from_heading_structure(self):
        from eahandbookcompiler.scraper import _extract_from_heading_structure

        html = """
        <div>
            <h2>Chapter One</h2>
            <ul><li><a href="/posts/abc/post-one">Post One</a></li></ul>
            <h3>Chapter Two</h3>
            <ul><li><a href="/posts/def/post-two">Post Two</a></li></ul>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = _extract_from_heading_structure(content)
        assert len(posts) == 2
        assert posts[0].section == "Chapter One"
        assert posts[1].section == "Chapter Two"


class TestExtractPostsFromContent:
    def test_delegates_to_react_structure_when_available(self):
        from unittest.mock import MagicMock, patch

        from eahandbookcompiler.scraper import extract_posts_from_content

        mock_content = MagicMock()
        expected_posts = [MagicMock()]

        with (
            patch(
                "eahandbookcompiler.scraper._extract_from_react_structure", return_value=expected_posts
            ) as mock_react,
            patch("eahandbookcompiler.scraper._extract_from_heading_structure") as mock_heading,
        ):
            posts = extract_posts_from_content(mock_content)

            assert posts == expected_posts
            mock_react.assert_called_once_with(mock_content)
            mock_heading.assert_not_called()

    def test_delegates_to_heading_structure_as_fallback(self):
        from unittest.mock import MagicMock, patch

        from eahandbookcompiler.scraper import extract_posts_from_content

        mock_content = MagicMock()
        expected_posts = [MagicMock()]

        with (
            patch("eahandbookcompiler.scraper._extract_from_react_structure", return_value=[]) as mock_react,
            patch(
                "eahandbookcompiler.scraper._extract_from_heading_structure", return_value=expected_posts
            ) as mock_heading,
        ):
            posts = extract_posts_from_content(mock_content)

            assert posts == expected_posts
            mock_react.assert_called_once_with(mock_content)
            mock_heading.assert_called_once_with(mock_content)

    def test_prefers_react_structure(self):
        from eahandbookcompiler.scraper import extract_posts_from_content

        html = """
        <div>
            <div class="LargeSequencesItem-columns">
                <div class="LargeSequencesItem-titleAndAuthor">
                    <a href="/s/intro">Intro</a>
                </div>
                <div class="LargeSequencesItem-right">
                    <a href="/posts/abc/react-post">React Post</a>
                </div>
            </div>
            <h2>Fallback</h2>
            <ul><li><a href="/posts/def/heading-post">Heading Post</a></li></ul>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = extract_posts_from_content(content)
        assert len(posts) == 1
        assert posts[0].title == "React Post"

    def test_falls_back_to_heading_structure(self):
        from eahandbookcompiler.scraper import extract_posts_from_content

        html = """
        <div>
            <h2>Section</h2>
            <ul><li><a href="/posts/abc/heading-post">Heading Post</a></li></ul>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = extract_posts_from_content(content)
        assert len(posts) == 1
        assert posts[0].title == "Heading Post"


class TestScrapeHandbookIndexContentDiv:
    def test_uses_content_div(self):
        html = """
        <html><body>
            <div class="PageContent">
                <h2>Section</h2>
                <ul><li><a href="/posts/abc/my-post">My Post</a></li></ul>
            </div>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        posts = scrape_handbook_index(session)
        assert len(posts) == 1
        assert posts[0].title == "My Post"

    def test_uses_large_sequences_item_body(self):
        html = """
        <html><body>
            <div class="LargeSequencesItem-columns">
                <div class="LargeSequencesItem-titleAndAuthor">
                    <a href="/s/intro">Intro</a>
                </div>
                <div class="LargeSequencesItem-right">
                    <a href="/posts/x/react-post">React Post</a>
                </div>
            </div>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        posts = scrape_handbook_index(session)
        assert len(posts) == 1
        assert posts[0].title == "React Post"

    def test_returns_empty_when_no_content(self):
        html = "<html></html>"
        session = MagicMock()
        session.get.return_value = _make_response(html)
        posts = scrape_handbook_index(session)
        assert posts == []


class TestCacheOperations:
    def test_load_cached_post_success(self, tmp_path):
        import json

        from eahandbookcompiler.scraper import _load_cached_post

        cache_path = tmp_path / "test.json"
        cache_path.write_text(
            json.dumps({"markdown": "cached md", "author": "Cached Author", "posted_date": "2023-01-01"}),
            encoding="utf-8",
        )
        post = Post(title="T", url="u")
        result = _load_cached_post(cache_path, post)
        assert result is True
        assert post.markdown == "cached md"
        assert post.author == "Cached Author"
        assert post.posted_date == "2023-01-01"

    def test_load_cached_post_missing_file(self, tmp_path):
        from eahandbookcompiler.scraper import _load_cached_post

        cache_path = tmp_path / "missing.json"
        post = Post(title="T", url="u")
        result = _load_cached_post(cache_path, post)
        assert result is False

    def test_load_cached_post_invalid_json(self, tmp_path):
        from eahandbookcompiler.scraper import _load_cached_post

        cache_path = tmp_path / "bad.json"
        cache_path.write_text("not valid json", encoding="utf-8")
        post = Post(title="T", url="u")
        result = _load_cached_post(cache_path, post)
        assert result is False

    def test_save_post_to_cache(self, tmp_path):
        import json

        from eahandbookcompiler.scraper import _save_post_to_cache

        cache_path = tmp_path / "saved.json"
        post = Post(title="T", url="u", markdown="md", author="A", posted_date="2023-01-01")
        _save_post_to_cache(cache_path, post)
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["markdown"] == "md"
        assert data["author"] == "A"

    def test_save_post_to_cache_os_error(self, tmp_path):
        from eahandbookcompiler.scraper import _save_post_to_cache

        cache_path = tmp_path / "nonexistent_dir" / "file.json"
        post = Post(title="T", url="u", markdown="md")
        # Should not raise, just silently fail
        _save_post_to_cache(cache_path, post)
        assert not cache_path.exists()


class TestProcessSinglePostCache:
    def test_uses_cache_when_available(self, tmp_path):
        import json

        from eahandbookcompiler.scraper import _process_single_post

        post = Post(title="T", url="https://forum.effectivealtruism.org/posts/abc/test")
        # Pre-populate cache
        import hashlib

        url_hash = hashlib.sha256(post.url.encode("utf-8")).hexdigest()
        cache_path = tmp_path / f"{url_hash}.json"
        cache_path.write_text(
            json.dumps({"markdown": "from cache", "author": "Cache", "posted_date": "2024-01-01"}),
            encoding="utf-8",
        )

        session = MagicMock()
        _process_single_post(post, session, tmp_path)

        assert post.markdown == "from cache"
        assert post.author == "Cache"
        session.get.assert_not_called()


class TestScrapeAllVerbose:
    def test_verbose_sequential(self, capsys):
        session = MagicMock()
        index_response = _make_response(SAMPLE_HANDBOOK_HTML)
        post_response = _make_response(SAMPLE_POST_HTML)
        session.get.side_effect = [index_response, post_response, post_response, post_response]

        handbook = scrape_all(session=session, delay=0, max_workers=1, verbose=True)

        assert len(handbook.posts) == 3
        captured = capsys.readouterr()
        assert "Fetching handbook index" in captured.out
        assert "Found 3 posts" in captured.out

    @patch("eahandbookcompiler.scraper.make_session")
    def test_verbose_concurrent(self, mock_make_session, capsys):
        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        handbook = scrape_all(session=index_session, delay=0, max_workers=2, verbose=True)

        assert len(handbook.posts) == 3
        captured = capsys.readouterr()
        assert "Fetching handbook index" in captured.out


def test_html_to_markdown_expands_abbr_tags():
    """Test that <abbr> tags with title attributes are expanded to 'Text (Title)'."""
    from bs4 import BeautifulSoup

    from eahandbookcompiler.scraper import html_to_markdown

    html_with_title = '<div>The <abbr title="World Health Organization">WHO</abbr> is an agency.</div>'
    soup_with_title = BeautifulSoup(html_with_title, "lxml").find("div")
    assert soup_with_title is not None
    md_with_title = html_to_markdown(soup_with_title)
    assert "The WHO (World Health Organization) is an agency." in md_with_title

    html_without_title = "<div>The <abbr>WHO</abbr> is an agency.</div>"
    soup_without_title = BeautifulSoup(html_without_title, "lxml").find("div")
    assert soup_without_title is not None
    md_without_title = html_to_markdown(soup_without_title)
    assert "The WHO is an agency." in md_without_title


def test_html_to_markdown_adds_fallback_alt_text():
    """Test that missing alt attributes get a fallback, while empty ones are preserved."""
    from bs4 import BeautifulSoup

    from eahandbookcompiler.scraper import html_to_markdown

    html_no_alt = '<img src="https://example.com/image.jpg" />'
    soup_no_alt = BeautifulSoup(html_no_alt, "lxml")
    md_no_alt = html_to_markdown(soup_no_alt)
    assert md_no_alt == "![Image](https://example.com/image.jpg)"

    html_empty_alt = '<img src="https://example.com/image.jpg" alt="" />'
    soup_empty_alt = BeautifulSoup(html_empty_alt, "lxml")
    md_empty_alt = html_to_markdown(soup_empty_alt)
    assert md_empty_alt == "![](https://example.com/image.jpg)"

    html_alt = '<img src="https://example.com/image.jpg" alt="A nice image" />'
    soup_alt = BeautifulSoup(html_alt, "lxml")
    md_alt = html_to_markdown(soup_alt)
    assert md_alt == "![A nice image](https://example.com/image.jpg)"


def test_html_to_markdown_preserves_semantic_inline_tags():
    """Test that semantic inline tags like kbd, q, cite, del, s, mark, u, ins are preserved."""
    from bs4 import BeautifulSoup

    from eahandbookcompiler.scraper import html_to_markdown

    html = "<div>Press <kbd>Ctrl</kbd> + <kbd>C</kbd> to copy. <q>Quote</q> from <cite>Book</cite>. <del>Deleted</del> and <s>Strikethrough</s>. <mark>Highlighted</mark>, <u>underlined</u>, and <ins>inserted</ins>.</div>"
    soup = BeautifulSoup(html, "lxml").find("div")
    assert soup is not None
    md = html_to_markdown(soup)
    assert "<kbd>Ctrl</kbd>" in md
    assert "<kbd>C</kbd>" in md
    assert "<q>Quote</q>" in md
    assert "<cite>Book</cite>" in md
    assert "<del>Deleted</del>" in md
    assert "<s>Strikethrough</s>" in md
    assert "<mark>Highlighted</mark>" in md
    assert "<u>underlined</u>" in md
    assert "<ins>inserted</ins>" in md


def test_html_to_markdown_xss_evasion():
    """Test that XSS evasion techniques on href/src attributes are stripped correctly."""
    html = """<div>
    <a href="jav	ascript:alert(1)">Click me6</a>
    <a href="java\nscript:alert(1)">Click me7</a>
    <a href="jav&#x0A;ascript:alert(1)">Click me8</a>
    <a href="  javascript:alert(1) ">Click me4</a>
    <a href="javascript:alert(1)">Click me5</a>
    <a href="%6Aavascrip%74:%61lert(1)">Click me6</a>
    <a href="&#x6A;avascrip&#x74;&#x3A;alert(1)">Click me7</a>
    <a href="vbscript:msgbox(1)">Click me8</a>
    <a href="file:///etc/passwd">LFI attempt</a>
    <a href="https://example.com">safe</a>
    <a href="mailto:test@example.com">safe mailto</a>
    <a href="/relative/path">relative</a>
    <a href="/out?url=javascript:alert(1)">outbound xss</a>
    <video poster="javascript:alert(1)" src="javascript:alert(2)"></video>
    <audio src="javascript:alert(1)"></audio>
    <track src="javascript:alert(1)">
    </div>"""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("div")
    assert tag is not None
    md = html_to_markdown(tag)

    assert "javascript:" not in md
    assert "vbscript:" not in md
    assert "file:" not in md
    assert "alert(1)" not in md
    assert "msgbox(1)" not in md
    assert "[safe](https://example.com)" in md
    assert "[safe mailto](mailto:test@example.com)" in md
    assert "[relative](https://forum.effectivealtruism.org/relative/path)" in md
    assert "outbound xss" in md
    assert "javascript:" not in md


class TestFetchUnsafePort:
    def test_unsafe_redirect_port_raises(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        redirect_response = MagicMock()
        redirect_response.__enter__ = MagicMock(return_value=redirect_response)
        redirect_response.__exit__ = MagicMock(return_value=None)
        redirect_response.is_redirect = True
        redirect_response.headers = MagicMock()
        redirect_response.headers.get.return_value = "https://forum.effectivealtruism.org:8080/post"
        session.get.return_value = redirect_response

        with pytest.raises(ValueError, match="Unsafe URL port: 8080"):
            fetch(session, "https://forum.effectivealtruism.org/post")


class TestIsEaForumPostPort:
    def test_non_standard_port_rejected(self):
        assert not is_ea_forum_post(
            "https://forum.effectivealtruism.org:9090/posts/abc/title",
        )


class TestFindLargestContentDivisionEdgeCases:
    def test_skips_html_comments(self):
        from eahandbookcompiler.scraper import find_largest_content_division

        html = "<html><body><div>text<!-- comment --></div></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = find_largest_content_division(soup)
        assert result is not None

    def test_skips_empty_text_nodes(self):
        from eahandbookcompiler.scraper import find_largest_content_division

        html = "<html><body><div><span></span>content</div></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = find_largest_content_division(soup)
        assert result is not None

    def test_returns_none_for_only_empty_text_divs(self):
        from eahandbookcompiler.scraper import find_largest_content_division

        html = "<html><body><div></div></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = find_largest_content_division(soup)
        # The div exists but has no text content, so div_text_lengths is empty
        assert result is None


class TestExtractFromReactStructureEmptyHref:
    def test_skips_empty_href_links(self):
        from eahandbookcompiler.scraper import _extract_from_react_structure

        html = """
        <div>
            <div class="LargeSequencesItem-columns">
                <div class="LargeSequencesItem-titleAndAuthor">
                    <a href="/s/intro">Intro</a>
                </div>
                <div class="LargeSequencesItem-right">
                    <a href="">Empty Link</a>
                    <a href="/posts/abc/valid">Valid Post</a>
                </div>
            </div>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = _extract_from_react_structure(content)
        assert len(posts) == 1
        assert posts[0].title == "Valid Post"


class TestExtractFromHeadingStructureEmptyHref:
    def test_skips_empty_href_links(self):
        from eahandbookcompiler.scraper import _extract_from_heading_structure

        html = """
        <div>
            <h2>Section</h2>
            <ul>
                <li><a href="">Empty</a></li>
                <li><a href="/posts/abc/valid">Valid</a></li>
            </ul>
        </div>
        """
        content = BeautifulSoup(html, "lxml").find("div")
        assert content is not None
        posts = _extract_from_heading_structure(content)
        assert len(posts) == 1
        assert posts[0].title == "Valid"


class TestScrapeHandbookIndexClassVariants:
    def test_string_class_attribute(self):
        """Test scrape_handbook_index with a div that has a string class containing 'content'."""
        html = """
        <html><body>
            <div class="mainContent">
                <h2>Section</h2>
                <ul><li><a href="/posts/abc/post">Post</a></li></ul>
            </div>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        posts = scrape_handbook_index(session)
        assert len(posts) == 1

    def test_content_div_with_toc_class_skipped(self):
        """A div with both 'content' and 'TableOfContents' in class should be skipped."""
        html = """
        <html><body>
            <div class="ContentTableOfContentsWrapper">
                <h2>TOC Section</h2>
                <ul><li><a href="/posts/toc/link">TOC Link</a></li></ul>
            </div>
            <main>
                <h2>Main Section</h2>
                <ul><li><a href="/posts/abc/real-post">Real Post</a></li></ul>
            </main>
        </body></html>
        """
        session = MagicMock()
        session.get.return_value = _make_response(html)
        posts = scrape_handbook_index(session)
        assert len(posts) == 1
        assert posts[0].title == "Real Post"


class TestScrapePostContentFallbacks:
    def test_scrape_post_content_no_body_no_divs(self):
        """When no post body or content div is found, a fallback message is produced."""
        html = "<html><body><p>Just text</p></body></html>"
        session = MagicMock()
        session.get.return_value = _make_response(html)

        post = Post(title="Test", url="https://forum.effectivealtruism.org/posts/x/y")
        result = scrape_post_content(post, session)
        # With no body/content divs, we expect the generic "Content could not be extracted" fallback message.
        assert "Content could not be extracted" in result.markdown

    def test_scrape_post_content_creates_session_when_none(self):
        """When session is None, scrape_post_content creates its own session."""
        with patch("eahandbookcompiler.scraper.make_session") as mock_make:
            mock_session = MagicMock()
            mock_session.get.return_value = _make_response(SAMPLE_POST_HTML)
            mock_make.return_value = mock_session

            post = Post(title="Test", url="https://forum.effectivealtruism.org/posts/x/y")
            result = scrape_post_content(post, session=None)

            mock_make.assert_called_once()
            assert result.markdown


class TestScrapeAllFallbacks:
    def test_scrape_all_creates_session_when_none(self):
        """When session is None, scrape_all creates its own session."""
        with patch("eahandbookcompiler.scraper.make_session") as mock_make:
            mock_session = MagicMock()
            index_response = _make_response(SAMPLE_HANDBOOK_HTML)
            post_response = _make_response(SAMPLE_POST_HTML)
            # SAMPLE_HANDBOOK_HTML has 3 posts, so we need 1 index + 3 post responses
            mock_session.get.side_effect = [index_response, post_response, post_response, post_response]
            mock_make.return_value = mock_session

            handbook = scrape_all(session=None, delay=0, max_workers=1)

            mock_make.assert_called()
            assert len(handbook.posts) == 3

    def test_scrape_all_non_verbose_error(self, capsys):
        """When not verbose and index fetch fails, 'Failed.' is printed."""
        import requests as req

        session = MagicMock()
        response = MagicMock()
        response.is_redirect = False
        response.raise_for_status.side_effect = req.exceptions.HTTPError("500 Server Error")
        session.get.return_value = response

        import click

        with pytest.raises(click.ClickException):
            scrape_all(session=session, delay=0, max_workers=1, verbose=False)

        captured = capsys.readouterr()
        assert "Failed." in captured.out


class TestFetchContentTypeValidation:
    def test_rejects_binary_content_type(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = MagicMock()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)
        response.is_redirect = False
        response.raise_for_status = MagicMock()
        response.headers = MagicMock()
        response.headers.get.return_value = "application/octet-stream"
        session.get.return_value = response

        with pytest.raises(ValueError, match="Unexpected Content-Type"):
            fetch(session, "https://forum.effectivealtruism.org/post")

    def test_rejects_image_content_type(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = MagicMock()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)
        response.is_redirect = False
        response.raise_for_status = MagicMock()
        response.headers = MagicMock()
        response.headers.get.return_value = "image/png"
        session.get.return_value = response

        with pytest.raises(ValueError, match="Unexpected Content-Type"):
            fetch(session, "https://forum.effectivealtruism.org/post")

    def test_allows_html_content_type(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = _make_response("<html><body>ok</body></html>")
        session.get.return_value = response

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "ok"

    def test_allows_missing_content_type(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = MagicMock()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)
        response.is_redirect = False
        response.raise_for_status = MagicMock()
        response.text = "<html><body>ok</body></html>"
        response.headers = MagicMock()
        response.headers.get.return_value = None
        response.encoding = "utf-8"
        response.iter_content.return_value = [b"<html><body>ok</body></html>"]
        session.get.return_value = response

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "ok"

    def test_allows_xhtml_content_type(self):
        from eahandbookcompiler.scraper import fetch

        session = MagicMock()
        response = MagicMock()
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)
        response.is_redirect = False
        response.raise_for_status = MagicMock()
        response.text = "<html><body>ok</body></html>"
        response.headers = MagicMock()
        response.headers.get.return_value = "application/xhtml+xml"
        response.encoding = "utf-8"
        response.iter_content.return_value = [b"<html><body>ok</body></html>"]
        session.get.return_value = response

        soup = fetch(session, "https://forum.effectivealtruism.org/post")
        assert soup.text == "ok"


class TestConcurrentThreadLocalSession:
    @patch("eahandbookcompiler.scraper.make_session")
    def test_thread_local_session_reused_within_thread(self, mock_make_session):
        """Each worker thread creates exactly one session via thread-local storage."""
        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        # With 1 worker, only 1 thread-local session should be created
        handbook = scrape_all(session=index_session, delay=0, max_workers=2)

        assert len(handbook.posts) == 3
        for post in handbook.posts:
            assert post.markdown
        # make_session should be called at most max_workers times (not once per post)
        assert mock_make_session.call_count <= 2


class TestConcurrentDelay:
    @patch("eahandbookcompiler.scraper.time.sleep")
    @patch("eahandbookcompiler.scraper.make_session")
    def test_concurrent_respects_delay(self, mock_make_session, mock_sleep):
        """Concurrent mode should sleep after each post to throttle requests."""
        from unittest.mock import call

        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        scrape_all(session=index_session, delay=0.5, max_workers=2)

        # Each post should trigger a sleep call with the specified delay
        sleep_calls = [c for c in mock_sleep.call_args_list if c == call(0.5)]
        assert len(sleep_calls) == 3  # one per post

    @patch("eahandbookcompiler.scraper.time.sleep")
    @patch("eahandbookcompiler.scraper.make_session")
    def test_concurrent_no_delay_when_zero(self, mock_make_session, mock_sleep):
        """Concurrent mode should skip sleep when delay is 0."""
        thread_session = MagicMock()
        thread_session.get.return_value = _make_response(SAMPLE_POST_HTML)
        mock_make_session.return_value = thread_session

        index_session = MagicMock()
        index_session.get.return_value = _make_response(SAMPLE_HANDBOOK_HTML)

        scrape_all(session=index_session, delay=0, max_workers=2)

        # No sleep calls should be made when delay is 0
        mock_sleep.assert_not_called()


class TestLFIPrevention:
    def test_outbound_redirect_lfi_prevention(self):
        """Test that unwrapping outbound links does not produce relative paths vulnerable to LFI."""
        from bs4 import BeautifulSoup

        from eahandbookcompiler.scraper import html_to_markdown

        # Simulating an unwrapped URL that points to a local file
        html = '<img src="https://forum.effectivealtruism.org/out?url=/etc/passwd">'
        soup = BeautifulSoup(html, "lxml")

        md = html_to_markdown(soup)

        # The result should be absolute and prefixed with BASE_URL, not just '/etc/passwd'
        assert md == "![Image](https://forum.effectivealtruism.org/etc/passwd)"


class TestIsEaForumPostEmptyHost:
    def test_empty_host_with_scheme_rejected(self):
        """Test that URLs with a scheme but no host (like http:///posts/) are rejected to prevent DoS."""
        from eahandbookcompiler.scraper import is_ea_forum_post

        assert not is_ea_forum_post("http:///posts/123")
        assert not is_ea_forum_post("https:///posts/123")

    def test_relative_path_allowed(self):
        """Test that valid relative paths without a scheme are still allowed."""
        from eahandbookcompiler.scraper import is_ea_forum_post

        assert is_ea_forum_post("/posts/123")
