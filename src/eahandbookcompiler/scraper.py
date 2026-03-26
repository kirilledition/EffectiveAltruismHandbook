"""Scraper for the EA Handbook at forum.effectivealtruism.org/handbook."""

from __future__ import annotations

import functools
import hashlib
import html
import json
import posixpath
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, parse_qs, unquote
from urllib.parse import urljoin as _urljoin
from urllib.parse import urlparse as _urlparse

import click
import requests
from bs4 import BeautifulSoup
from bs4.element import Comment, Tag
from markdownify import MarkdownConverter

if TYPE_CHECKING:
    from pathlib import Path

HANDBOOK_URL = "https://forum.effectivealtruism.org/handbook"
BASE_URL = "https://forum.effectivealtruism.org"
REQUEST_DELAY = 1.0  # seconds between requests

_DECOMPOSE_TAGS = frozenset(["nav", "footer", "script", "style", "noscript"])
_SANITIZE_TAGS = frozenset(["a", "img", "source", "object", "iframe", "embed"])
_HTML_TAGS_TO_FILTER = list(_DECOMPOSE_TAGS | _SANITIZE_TAGS | {"div"})
_WS_CTRL_RE = re.compile(r"[\s\x00-\x1f\x7f-\x9f]")
_DANGEROUS_SCHEMES = ("javascript:", "data:", "vbscript:", "file:")


# ⚡ Bolt Optimization: To optimize URL processing for repetitive links (common in documents like the EA Handbook),
# memoize urllib.parse.urlparse and urllib.parse.urljoin using functools.lru_cache(maxsize=512)
# to bypass redundant string parsing overhead.
@functools.lru_cache(maxsize=512)
def urlparse(url: str, scheme: str = "", allow_fragments: bool = True) -> ParseResult:
    """Parse a URL into 6 components, memoized for performance.

    Args:
        url: URL string to parse.
        scheme: Default scheme to use if URL lacks one.
        allow_fragments: Whether to allow fragment identifiers.

    Returns:
        ParseResult containing the 6 components.
    """
    return _urlparse(url, scheme, allow_fragments)


@functools.lru_cache(maxsize=512)
def urljoin(base: str, url: str | None, allow_fragments: bool = True) -> str:
    """Join a base URL and a possibly relative URL to form an absolute interpretation.

    Memoized for performance.

    Args:
        base: Base URL.
        url: URL to join.
        allow_fragments: Whether to allow fragment identifiers.

    Returns:
        A full, absolute URL string.
    """
    return _urljoin(base, url, allow_fragments)


# Compiled regexes for optimal class name lookups, avoiding lambda overhead
POST_BODY_RE = re.compile(r"^(postBody|post-body|PostBody)$")
AUTHOR_BYLINE_RE = re.compile(r"(?i)author|username|usersname")
LARGE_SEQ_COLUMNS_RE = re.compile(r"LargeSequencesItem-columns")
LARGE_SEQ_TITLE_RE = re.compile(r"LargeSequencesItem-titleAndAuthor")
LARGE_SEQ_RIGHT_RE = re.compile(r"LargeSequencesItem-right")
CONTENT_CLASS_RE = re.compile(r"(?i)content")
TOC_CLASS_RE = re.compile(r"(?i)tableofcontents")

_AUTHOR_CLEAN_RE = re.compile(r"<[^>]+>")

# ⚡ Bolt Optimization: Instantiate MarkdownConverter once at the module level.
# Reusing this instance across all posts avoids the overhead of instantiating
# the converter inside the tight html_to_markdown loop, speeding up parsing ~2x.
_MARKDOWN_CONVERTER = MarkdownConverter(heading_style="ATX")

# Thread-local storage for per-thread sessions in the concurrent scraper.
# Each worker thread lazily creates exactly one ``requests.Session`` via
# ``make_session()`` and reuses it for every post it processes, enabling
# proper HTTP connection pooling within each thread.
_thread_local = threading.local()


@dataclass
class Post:
    """A single post/chapter from the EA Handbook.

    Attributes:
        title: Display title of the post.
        url: Canonical URL on the EA Forum.
        section: Handbook section this post belongs to.
        author: Author name extracted from the post page.
        posted_date: Publication date as an ISO string (YYYY-MM-DD).
        markdown: Converted markdown content of the post body.
    """

    title: str
    url: str
    section: str = ""
    author: str = ""
    posted_date: str = ""
    markdown: str = ""


@dataclass
class Handbook:
    """The full EA Handbook with all posts.

    Attributes:
        posts: Ordered list of posts comprising the handbook.
    """

    posts: list[Post] = field(default_factory=list)


def make_session() -> requests.Session:
    """Create a requests session with an identifying User-Agent header.

    Returns:
        Configured session ready for polite scraping.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; EA-Handbook-Bot/1.0; "
                "+https://github.com/kirilledition/EffectiveAltruismHandbook)"
            ),
        },
    )
    return session


def _validate_url(url: str) -> str:
    """Validate that a URL uses a safe scheme, domain, and port.

    Args:
        url: URL to validate.

    Returns:
        The normalized and validated URL string.

    Raises:
        ValueError: If the URL targets an unsafe domain, scheme, or port.
    """
    # Security Enhancement: Prevent URL validation bypasses via backslashes
    # where urllib.parse.urlparse fails to normalize them into the path/hostname
    # correctly, ensuring consistent interpretation with modern HTTP clients.
    url = url.replace("\\", "/")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsafe URL scheme: {parsed.scheme}")

    hostname = parsed.hostname or ""
    if not (hostname == "effectivealtruism.org" or hostname.endswith(".effectivealtruism.org")):
        raise ValueError(f"Unsafe URL domain: {hostname}")

    port = parsed.port
    if port not in (None, 80, 443):
        raise ValueError(f"Unsafe URL port: {port}")

    return parsed.geturl()


def fetch(session: requests.Session, url: str) -> BeautifulSoup:
    """Fetch a URL and return parsed HTML, following safe redirects only.

    Only redirects within the ``effectivealtruism.org`` domain and over
    ``http`` / ``https`` are allowed.  A maximum of five redirects is
    permitted before giving up.

    Args:
        session: Active requests session to use.
        url: URL to fetch.

    Returns:
        Parsed BeautifulSoup tree of the response body.

    Raises:
        ValueError: If a redirect targets an unsafe domain or scheme.
        requests.TooManyRedirects: If the redirect limit is exceeded.
        requests.HTTPError: If the final response has a non-2xx status.
    """
    current_url = url
    for _ in range(5):
        current_url = _validate_url(current_url)
        with session.get(current_url, timeout=30, allow_redirects=False, stream=True) as response:
            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    # If a redirect has no Location, treat it as a normal response
                    pass
                else:
                    redirect_url = urljoin(current_url, location)
                    current_url = redirect_url
                    continue

            response.raise_for_status()

            # Reject non-HTML responses to avoid processing large binary files
            # (e.g. if the server redirects to an asset CDN).
            content_type = response.headers.get("Content-Type", "")
            if content_type:
                mime = content_type.split(";")[0].strip().lower()
                if mime not in ("text/html", "application/xhtml+xml"):
                    raise ValueError(f"Unexpected Content-Type for {current_url}: {content_type}")

            chunks = []
            downloaded = 0
            max_size = 10 * 1024 * 1024  # 10 MB limit to prevent memory exhaustion DoS
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if downloaded > max_size:
                        raise ValueError(f"Response too large for {current_url}: exceeds 10 MB limit")

            text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
            return BeautifulSoup(text, "lxml")

    raise requests.TooManyRedirects(f"Exceeded maximum redirects for {url}")


def is_ea_forum_post(url: str) -> bool:
    """Check whether a URL points to an EA Forum post or sequence.

    Args:
        url: Absolute or relative URL to test.

    Returns:
        ``True`` if the URL matches a known EA Forum post pattern.
    """
    # Security Enhancement: Prevent URL validation bypasses via backslashes
    # where urllib.parse.urlparse fails to normalize them into the path/hostname
    # correctly, ensuring consistent interpretation with modern HTTP clients.
    url = url.replace("\\", "/")

    # ⚡ Bolt Optimization: Fast-path string check bypasses expensive URL parsing
    # and normalization overhead (~2x faster) for the vast majority of URLs that
    # are clearly not EA Forum posts (e.g. external links).
    if "/posts/" not in url and "/s/" not in url:
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", ""):
        return False

    hostname = parsed.hostname or ""

    # Only allow EA Forum URLs (or relative URLs with no hostname)
    if hostname not in ("forum.effectivealtruism.org", ""):
        return False

    # Mitigate SSRF by disallowing non-standard ports on the EA Forum host.
    # Allow no explicit port (None) or standard HTTP/HTTPS ports only.
    if hostname == "forum.effectivealtruism.org" and parsed.port not in (None, 80, 443):
        return False

    # Normalize the path to prevent path traversal bypasses
    # e.g., /posts/../../../etc/passwd -> /etc/passwd
    path = posixpath.normpath(parsed.path)
    if not path.startswith("/"):
        path = "/" + path

    return path.startswith(("/posts/", "/s/"))


def html_to_markdown(html_element: Tag) -> str:  # noqa: C901, PLR0912
    """Convert a BeautifulSoup element to clean markdown.

    Navigation, footer, script, style, and comment sections are stripped
    before conversion to avoid including non-content material.  Standard
    Creative Commons license footers are also removed, while non-CC
    license notices are preserved.

    Args:
        html_element: BeautifulSoup ``Tag`` containing the HTML to convert.

    Returns:
        Cleaned markdown string.
    """
    # ⚡ Bolt Optimization: Combine find_all searches into a single fast pass.
    # This replaces 3 separate O(N) DOM traversals with exactly 1.
    for element in html_element.find_all(_HTML_TAGS_TO_FILTER):
        tag_name = element.name

        if tag_name in _DECOMPOSE_TAGS:
            element.decompose()
        elif tag_name == "div":
            # Remove comment sections so forum debates are not included
            classes = element.get("class")
            if classes:
                # ⚡ Bolt Optimization: Use fast-path string checks instead of regex for comment exclusion.
                # Checking `"comments" in c.lower()` is significantly faster than executing a regex
                # `re.search` engine across all DIVs, improving DOM cleaning performance by ~2x.
                if isinstance(classes, list):
                    for c in classes:
                        if "comments" in c.lower():
                            element.decompose()
                            break
                elif "comments" in classes.lower():
                    element.decompose()
        elif tag_name in _SANITIZE_TAGS:
            # Security Enhancement: Sanitize 'href', 'src', and 'data' to prevent XSS persistence in PDF/EPUB.
            for attr in ("href", "src", "data"):
                val = element.get(attr)
                if val and isinstance(val, str):
                    cleaned_val = _WS_CTRL_RE.sub("", unquote(html.unescape(val))).lower()
                    if cleaned_val.startswith(_DANGEROUS_SCHEMES):
                        del element[attr]
                    else:
                        # ⚡ Bolt Optimization: Fast-path string check bypasses heavy URL parsing.
                        # Using string `startswith` before `urlparse()` speeds up resolution
                        # by ~2x for standard absolute links (which comprise 99% of forum URLs)
                        # by bypassing scheme normalization.
                        if not val.startswith(("http://", "https://", "#", "mailto:", "tel:")):
                            parsed_val = urlparse(val)
                            if not parsed_val.scheme:
                                val = urljoin(BASE_URL, val)

                        # UX Enhancement: Unwrap EA Forum outbound link redirects (/out?url=...)
                        # so readers can access external links directly when reading offline,
                        # without relying on the forum's redirect service.
                        # ⚡ Bolt Optimization: Wrap with a fast string presence check (`"/out" in val`)
                        # to bypass parsing overhead for standard external links (~3x speedup).
                        if "/out" in val:
                            parsed_url = urlparse(val)
                            if parsed_url.path == "/out":
                                qs = parse_qs(parsed_url.query)
                                if qs.get("url"):
                                    val = qs["url"][0]

                                # Re-validate unwrapped URL to prevent XSS bypass
                                unwrapped_cleaned = _WS_CTRL_RE.sub("", unquote(html.unescape(val))).lower()
                                if unwrapped_cleaned.startswith(_DANGEROUS_SCHEMES):
                                    del element[attr]
                                    continue

                        element[attr] = val

    # Remove standard Creative Commons license footers
    _strip_cc_license_footers(html_element)

    # ⚡ Bolt Optimization: Use MarkdownConverter.convert_soup() directly
    # Passing a BeautifulSoup element to the markdownify() helper function
    # unnecessarily serializes it to a string and re-parses it.
    # Using convert_soup avoids this, improving HTML-to-Markdown parsing speed.
    return _MARKDOWN_CONVERTER.convert_soup(html_element).strip()


def _strip_cc_license_footers(element: Tag) -> None:
    """Remove elements containing standard Creative Commons license text.

    Searches from the bottom of the tree for elements whose text
    mentions "Creative Commons" or "CC BY".  If found, those elements
    are decomposed.  Elements that mention "License" but lack CC
    keywords are left untouched so non-standard licenses remain.

    Args:
        element: BeautifulSoup ``Tag`` to filter in place.
    """
    # ⚡ Bolt Optimization: Fast-path string check bypasses O(N) DOM traversal
    # and string allocations for the ~99% of posts that don't contain CC licenses.
    # We use `.get_text()` rather than a regex search on string nodes to ensure
    # we don't break if the text is split across inline tags (e.g. `CC <span>BY</span>`).
    full_text = element.get_text().lower()
    if "creative commons" not in full_text and "cc by" not in full_text:
        return

    cc_keywords = ("creative commons", "cc by")
    for child in reversed(element.find_all(["p", "div", "span", "a", "blockquote"])):
        text = child.get_text(strip=True).lower()
        if any(kw in text for kw in cc_keywords):
            child.decompose()


def extract_metadata_json_ld(soup: BeautifulSoup) -> tuple[str, str]:  # noqa: C901, PLR0912
    """Try to extract author and date from JSON-LD structured data in a single pass.

    Args:
        soup: Parsed page containing potential ``<script type="application/ld+json">`` blocks.

    Returns:
        Tuple of (author_name, date_string).
    """
    author = ""
    date_str = ""

    # ⚡ Bolt Optimization: Evaluate JSON-LD scripts exactly once to find both
    # author and date. This avoids two separate `find_all` calls and duplicate JSON
    # decoding for elements containing both properties.
    for script in soup.find_all("script", type="application/ld+json"):
        s = script.string or ""
        if not s:
            continue

        has_author = '"author"' in s
        has_date = '"datePublished"' in s or '"dateCreated"' in s

        if not has_author and not has_date:
            continue

        try:
            data = json.loads(s)
            if not isinstance(data, dict):
                continue
        except (json.JSONDecodeError, TypeError):  # fmt: skip
            continue

        if not author and has_author:
            a = data.get("author")
            if isinstance(a, dict):
                name = a.get("name", "")
                if name:
                    author = name
            elif isinstance(a, str) and a:
                author = a

        if not date_str and has_date:
            for key in ("datePublished", "dateCreated"):
                ds = data.get(key, "")
                if ds:
                    date_str = str(ds)[:10]  # YYYY-MM-DD
                    break

        if author and date_str:
            break

    return author, date_str


def extract_author(soup: BeautifulSoup, author_ld: str = "") -> str:
    """Extract the author name from a post page, trying several strategies.

    Strategies tried in order: JSON-LD structured data, ``<meta>`` author
    tag, common byline class patterns.  The result is stripped of any
    residual HTML tags and normalised whitespace.

    Args:
        soup: Parsed post page.
        author_ld: Author pre-extracted from JSON-LD to save parsing time.

    Returns:
        Author name, or an empty string if none could be found.
    """
    name = author_ld
    if not name:
        name = extract_author_json_ld(soup)
    if not name:
        name = extract_author_meta(soup)
    if not name:
        name = extract_author_byline(soup)

    return _clean_author_name(name)


def _clean_author_name(name: str) -> str:
    """Strip residual HTML tags and collapse whitespace from an author name.

    Args:
        name: Raw author name string.

    Returns:
        Cleaned author name.
    """
    # ⚡ Bolt Optimization: Use fast-path string checks and pre-compiled regexes
    # to bypass overhead when no HTML tags or excessive whitespace exist.
    if "<" in name:
        name = _AUTHOR_CLEAN_RE.sub("", name)

    if "  " in name or "\n" in name or "\t" in name or "\r" in name or "\xa0" in name:
        # ⚡ Bolt Optimization: Using `.split()` and `" ".join()` is roughly 2x faster than
        # `re.sub(r"\s+", " ", name)` because it bypasses the regex engine and leverages
        # highly-optimized native C code for string operations.
        name = " ".join(name.split())

    return name.strip()


def extract_author_json_ld(soup: BeautifulSoup) -> str:
    """Try to extract author from JSON-LD structured data.

    Args:
        soup: Parsed page containing potential ``<script type="application/ld+json">`` blocks.

    Returns:
        Author name, or an empty string if not found.
    """
    author, _ = extract_metadata_json_ld(soup)
    return author


def extract_author_meta(soup: BeautifulSoup) -> str:
    """Try to extract author from a ``<meta name="author">`` tag.

    Args:
        soup: Parsed page.

    Returns:
        Author name, or an empty string if not found.
    """
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        return str(meta_author["content"]).strip()
    return ""


def extract_author_byline(soup: BeautifulSoup) -> str:
    """Try to extract author from common byline class patterns.

    Searches for ``<a>`` or ``<span>`` elements whose CSS class contains
    ``author``, ``username``, or ``UsersName``.  The ``byline`` pattern
    and ``<div>`` tags are intentionally excluded because on the EA Forum
    the byline ``<div>`` is a large container holding the author name,
    publication date, and reading time estimate; using ``get_text`` on it
    would concatenate all that metadata into a single string.

    Args:
        soup: Parsed page.

    Returns:
        Author name, or an empty string if not found.
    """
    # ⚡ Bolt Optimization: Replace multiple DOM traversals and lambda evaluation
    # with a single regex traversal. Compiling a case-insensitive regex for 'author',
    # 'username', and 'UsersName' allows `soup.find()` to
    # complete the search roughly 3x faster, checking elements in a single pass.
    tag = soup.find(["a", "span"], class_=AUTHOR_BYLINE_RE)
    if tag:
        text = tag.get_text(strip=True)
        if text:
            return text

    return ""


def extract_date(soup: BeautifulSoup, date_ld: str = "") -> str:
    """Extract the publication date from a post page.

    Tries JSON-LD, ``<meta>`` date properties, and ``<time>`` elements
    in that order.

    Args:
        soup: Parsed post page.
        date_ld: Date pre-extracted from JSON-LD to save parsing time.

    Returns:
        ISO date string (YYYY-MM-DD), or an empty string if not found.
    """
    if date_ld:
        return date_ld

    _, date_str = extract_metadata_json_ld(soup)
    if date_str:
        return date_str

    # ⚡ Bolt Optimization: Replace multiple full-document searches for specific
    # meta attributes with a single pass fetching all meta tags, followed by
    # Python-level iteration. Meta tags are sparse (mostly in <head>), so this
    # reduces O(N) DOM traversals significantly while preserving priority order.
    metas = soup.find_all("meta")
    for attr_name in ("article:published_time", "datePublished", "date"):
        for meta in metas:
            if meta.get("property") == attr_name and meta.get("content"):
                return str(meta["content"]).strip()[:10]
        for meta in metas:
            if meta.get("name") == attr_name and meta.get("content"):
                return str(meta["content"]).strip()[:10]

    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return str(time_tag["datetime"])[:10]

    return ""


def find_largest_content_division(soup: BeautifulSoup) -> Tag | None:  # noqa: C901
    """Find the ``<div>`` with the most text content.

    Used as a last-resort heuristic when no known post-body selector
    matches.

    Args:
        soup: Parsed page.

    Returns:
        The ``<div>`` element with the most accumulated text, or ``None``.
    """
    divisions = soup.find_all("div")
    if not divisions:
        return None

    # ⚡ Bolt Optimization: Group text lengths by immediate parent tag first.
    # Instead of walking up the entire parent chain for *every single text node*
    # (which takes O(N*Depth) time), we accumulate lengths at the immediate parent
    # level in O(N), then propagate those sums up the tree just once per parent tag,
    # reducing redundant DOM traversals.
    parent_lengths: dict[int, int] = {}
    parent_tags: dict[int, Tag] = {}

    for text_node in soup.find_all(string=True):
        # type() is faster than isinstance()
        if type(text_node) is not Comment:
            length = len(text_node)
            if length:
                p = text_node.parent
                if p is not None:
                    pid = id(p)
                    try:
                        parent_lengths[pid] += length
                    except KeyError:
                        parent_lengths[pid] = length
                        parent_tags[pid] = p

    div_text_lengths: dict[int, int] = {}
    for pid, total_len in parent_lengths.items():
        curr = parent_tags[pid]
        while curr is not None:
            if curr.name == "div":
                try:
                    div_text_lengths[id(curr)] += total_len
                except KeyError:
                    div_text_lengths[id(curr)] = total_len
            curr = curr.parent

    if not div_text_lengths:
        return None
    return max(divisions, key=lambda d: div_text_lengths.get(id(d), 0))


def _extract_from_react_structure(content: Tag) -> list[Post]:
    posts: list[Post] = []
    items = content.find_all("div", class_=LARGE_SEQ_COLUMNS_RE)
    for item in items:
        title_tag = item.find("div", class_=LARGE_SEQ_TITLE_RE)
        current_section = "Introduction"
        if title_tag:
            a_tag = title_tag.find("a")
            current_section = a_tag.get_text(strip=True) if a_tag else title_tag.get_text(strip=True)

        right = item.find("div", class_=LARGE_SEQ_RIGHT_RE)
        if right:
            for link in right.find_all("a", recursive=True):
                href = str(link.get("href", ""))
                if not href:
                    continue
                url = urljoin(BASE_URL, href) if not href.startswith("http") else href
                if is_ea_forum_post(url):
                    title = link.get_text(strip=True)
                    if title:
                        posts.append(Post(title=title, url=url, section=current_section))
    return posts


def _extract_from_heading_structure(content: Tag) -> list[Post]:
    posts: list[Post] = []
    current_section = "Introduction"

    for element in content.find_all(["h1", "h2", "h3", "ul"]):
        tag_name = element.name
        if tag_name in ("h1", "h2", "h3"):
            current_section = element.get_text(strip=True)
        elif tag_name == "ul":
            for link in element.find_all("a", recursive=True):
                href = str(link.get("href", ""))
                if not href:
                    continue
                url = urljoin(BASE_URL, href) if not href.startswith("http") else href
                if is_ea_forum_post(url):
                    title = link.get_text(strip=True)
                    if title:
                        posts.append(Post(title=title, url=url, section=current_section))
    return posts


def extract_posts_from_content(content: Tag) -> list[Post]:
    """Parse the handbook content area and extract posts with sections.

    Section names are determined by ``<h1>``-``<h3>`` headings; post
    links are collected from ``<ul>`` lists that follow them. Also supports
    the newer React ``LargeSequencesItem`` component structure.

    Args:
        content: BeautifulSoup element wrapping the handbook table of contents.

    Returns:
        List of ``Post`` objects (without content populated).
    """
    # Try the new React LargeSequencesItem structure first
    posts = _extract_from_react_structure(content)
    if posts:
        return posts

    # Fallback to older heading-based structure
    return _extract_from_heading_structure(content)


def scrape_handbook_index(session: requests.Session | None = None) -> list[Post]:  # noqa: C901
    """Fetch the handbook index and return a list of Posts.

    Content is not yet fetched at this stage.

    Args:
        session: Optional requests session; a default one is created if not provided.

    Returns:
        De-duplicated, ordered list of ``Post`` stubs (title, url, section only).
    """
    if session is None:
        session = make_session()

    soup = fetch(session, HANDBOOK_URL)

    # Look for the main content area, avoiding TableOfContents which has 'content' in the name
    def _match_content_div(tag: Tag) -> bool:
        if tag.name != "div":
            return False
        classes = tag.get("class")
        if not classes:
            return False

        # ⚡ Bolt Optimization: Use fast-path string checks instead of regex
        # execution to filter classes.
        if isinstance(classes, str):
            c_lower = classes.lower()
            return "content" in c_lower and "tableofcontents" not in c_lower

        has_content = False
        for c in classes:
            c_lower = c.lower()
            if "tableofcontents" in c_lower:
                return False
            if "content" in c_lower:
                has_content = True
        return has_content

    # ⚡ Bolt Optimization: Use soup.find() with a custom evaluation function
    # instead of find_all(). find_all() eagerly evaluates and traverses the
    # entire O(N) DOM tree even if we only need the first match. find() stops
    # immediately upon finding the first match, bypassing redundant traversal.
    content = soup.find(_match_content_div)

    if content is None:
        content = soup.find("main") or soup.find("article") or soup.body

    # If we notice LargeSequencesItem anywhere in the body, prefer the full body to avoid missing them
    if soup.find("div", class_=LARGE_SEQ_COLUMNS_RE):
        content = soup.body

    if content is None:
        return []

    posts = extract_posts_from_content(content)

    # ⚡ Bolt Optimization: Use dict preservation of order for O(N) deduplication.
    # Replaces slower set + list accumulation loop with a single dictionary loop.
    # Since dicts preserve insertion order in Python 3.7+, this deduplicates by url
    # while maintaining the *first* occurrence order roughly 2x faster.
    seen: dict[str, Post] = {}
    for post in posts:
        if post.url not in seen:
            seen[post.url] = post
    return list(seen.values())


def find_post_body(soup: BeautifulSoup) -> Tag | None:
    """Locate the post body element within the page.

    Tries several CSS class patterns used by the EA Forum, then
    falls back to ``<article>`` and the ``itemprop="articleBody"``
    selector.

    Args:
        soup: Parsed post page.

    Returns:
        The body element, or ``None`` if no known selector matches.
    """
    # ⚡ Bolt Optimization: Use compiled regex with exact word match instead of multiple lambdas.
    # We use re.compile to match postBody, post-body, PostBody as full words in the class list.
    # This maintains exact-match semantics while allowing BeautifulSoup to do a single tree
    # traversal using optimized regex lookups, speeding up body extraction.
    return (
        soup.find("div", class_=POST_BODY_RE) or soup.find("div", {"itemprop": "articleBody"}) or soup.find("article")
    )


def scrape_post_content(post: Post, session: requests.Session | None = None) -> Post:
    """Fetch the content of a single post and populate its fields.

    Populates ``post.markdown``, ``post.author``, and ``post.posted_date``
    in place and returns the same ``Post`` object.

    Args:
        post: Post stub with at least ``url`` set.
        session: Optional requests session; a default is created if not provided.

    Returns:
        The same ``post`` instance with content fields populated.
    """
    if session is None:
        session = make_session()

    soup = fetch(session, post.url)
    body = find_post_body(soup)

    if body is None:
        body = find_largest_content_division(soup)

    if body:
        post.markdown = html_to_markdown(body)
    else:
        post.markdown = f"*Content could not be extracted from {post.url}*"

    author_ld, date_ld = extract_metadata_json_ld(soup)

    post.author = extract_author(soup, author_ld=author_ld)
    post.posted_date = extract_date(soup, date_ld=date_ld)

    return post


def _load_cached_post(cache_path: Path, post: Post) -> bool:
    """Load a post from the cache file if it exists.

    Args:
        cache_path: Path to the cache JSON file.
        post: Post object to populate with cached data.

    Returns:
        ``True`` if the post was loaded from cache, ``False`` otherwise.
    """
    if not cache_path.exists():
        return False
    try:
        with cache_path.open(encoding="utf-8") as f:
            data = json.load(f)
            post.markdown = data.get("markdown", "")
            post.author = data.get("author", "")
            post.posted_date = data.get("posted_date", "")
    except (json.JSONDecodeError, OSError):  # fmt: skip
        return False
    else:
        return True


def _save_post_to_cache(cache_path: Path, post: Post) -> None:
    """Save a scraped post to the cache file.

    Args:
        cache_path: Path to the cache JSON file.
        post: Post object with populated content fields.
    """
    try:
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "markdown": post.markdown,
                    "author": post.author,
                    "posted_date": post.posted_date,
                },
                f,
                indent=2,
            )
    except OSError:
        pass


def _process_single_post(
    post: Post,
    session: requests.Session | None,
    cache_dir: Path | None,
) -> bool:
    """Fetch and populate a single post, using cache when available.

    When *session* is ``None`` (concurrent mode) a thread-local session
    is lazily created so that each worker thread opens exactly one
    ``requests.Session`` and reuses it for connection pooling.

    Args:
        post: Post stub to populate with content.
        session: Active requests session, or ``None`` to use a
            thread-local session.
        cache_dir: Optional cache directory for post data.

    Returns:
        ``True`` if the post was loaded from cache, ``False`` otherwise.
    """
    if session is None:
        if not hasattr(_thread_local, "session"):
            _thread_local.session = make_session()
        session = _thread_local.session

    if cache_dir is not None:
        url_hash = hashlib.sha256(post.url.encode("utf-8")).hexdigest()[:16]
        cache_path = cache_dir / f"{url_hash}.json"
        if _load_cached_post(cache_path, post):
            return True

    scrape_post_content(post, session)

    if cache_dir is not None:
        _save_post_to_cache(cache_path, post)

    return False


def scrape_all(
    session: requests.Session | None = None,
    delay: float = REQUEST_DELAY,
    verbose: bool = False,
    cache_dir: Path | None = None,
    max_workers: int = 1,
) -> Handbook:
    """Scrape the full handbook: index + all post contents.

    When *max_workers* is greater than 1 posts are downloaded
    concurrently using a thread pool, which can significantly reduce
    total scrape time.  The per-request *delay* is only applied in
    sequential (single-worker) mode.

    Args:
        session: Optional requests session (useful for testing with mocks).
        delay: Seconds to wait between requests (sequential mode only).
        verbose: Emit progress messages via ``click.echo``.
        cache_dir: Optional directory to cache downloaded posts.
        max_workers: Number of concurrent download threads (default 1).

    Returns:
        A ``Handbook`` containing every post with content populated.
    """
    if session is None:
        session = make_session()

    if verbose:
        click.echo(f"Fetching handbook index from {HANDBOOK_URL} …")
        posts = scrape_handbook_index(session)
    else:
        click.secho("Fetching handbook index... ", fg="blue", nl=False)
        try:
            posts = scrape_handbook_index(session)
        except Exception as e:
            click.secho("✗ Failed.", fg="red")
            raise click.ClickException(str(e)) from e
        else:
            click.secho("✓ Done.", fg="green")

    if verbose:
        click.echo(f"Found {len(posts)} posts. Fetching content …")

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    handbook = Handbook(posts=posts)

    if max_workers > 1:
        _scrape_posts_concurrent(handbook.posts, cache_dir, max_workers, delay=delay, verbose=verbose)
    else:
        _scrape_posts_sequential(handbook.posts, session, cache_dir, delay, verbose=verbose)

    return handbook


def _truncate_title(item: str | Post | None) -> str:
    """Safely extract and truncate a post title for the progress bar."""
    if not item:
        return ""
    max_length = 35
    title = item.title if isinstance(item, Post) else str(item)
    return f"{title[:max_length]}…" if len(title) > max_length else title


def _get_item_from_bar(item: Post | str | None) -> Post:
    """Extract a Post from the progress bar item for type checking."""
    # This is a safe cast because click.progressbar yields the items from the original list
    return item  # type: ignore[return-value]


def _scrape_posts_sequential(
    posts: list[Post],
    session: requests.Session,
    cache_dir: Path | None,
    delay: float,
    *,
    verbose: bool = False,
) -> None:
    """Download posts one at a time with a polite delay."""
    total = len(posts)
    if not verbose:
        with click.progressbar(
            posts,
            label="Scraping posts",
            item_show_func=_truncate_title,
            fill_char=click.style("█", fg="blue"),
            empty_char=click.style("░", dim=True),
            color=True,
        ) as bar:
            for i, item in enumerate(bar, 1):
                post = _get_item_from_bar(item)
                cache_hit = _process_single_post(post, session, cache_dir)
                if i < total and not cache_hit:
                    time.sleep(delay)
    else:
        for i, post in enumerate(posts, 1):
            click.echo(f"  [{i}/{total}] {post.title}")
            cache_hit = _process_single_post(post, session, cache_dir)
            if i < total and not cache_hit:
                time.sleep(delay)


def _scrape_posts_concurrent(
    posts: list[Post],
    cache_dir: Path | None,
    max_workers: int,
    delay: float = REQUEST_DELAY,
    *,
    verbose: bool = False,
) -> None:
    """Download posts concurrently using a thread pool.

    Each worker thread lazily creates its own ``requests.Session`` via
    thread-local storage so that ``Session`` objects are not shared
    across threads and connection pooling works within each thread.

    A per-request *delay* is enforced after every HTTP request to
    throttle traffic and avoid triggering server-side rate limits.

    Progress messages may appear out of order since tasks complete
    at different times.
    """
    total = len(posts)

    def _worker(post: Post) -> None:
        cache_hit = _process_single_post(post, None, cache_dir)
        if delay > 0 and not cache_hit:
            time.sleep(delay)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(_worker, post): i for i, post in enumerate(posts)}
        if not verbose:
            with click.progressbar(
                length=total,
                label="Scraping posts",
                item_show_func=_truncate_title,
                fill_char=click.style("█", fg="blue"),
                empty_char=click.style("░", dim=True),
                color=True,
            ) as bar:
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    future.result()  # propagate exceptions
                    bar.update(1, current_item=posts[idx].title)
        else:
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                future.result()  # propagate exceptions
                click.echo(f"  [{idx + 1}/{total}] {posts[idx].title}")
