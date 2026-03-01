"""Scraper for the EA Handbook at forum.effectivealtruism.org/handbook."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
from urllib.parse import urljoin, urlparse

import click
import requests
from bs4 import BeautifulSoup
from bs4.element import Comment, Tag
from markdownify import markdownify

HANDBOOK_URL = "https://forum.effectivealtruism.org/handbook"
BASE_URL = "https://forum.effectivealtruism.org"
REQUEST_DELAY = 1.0  # seconds between requests


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
        response = session.get(current_url, timeout=30, allow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                break

            redirect_url = urljoin(current_url, location)
            parsed = urlparse(redirect_url)

            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Unsafe redirect scheme: {parsed.scheme}")

            netloc = parsed.netloc.split(":")[0]
            if not (netloc == "effectivealtruism.org" or netloc.endswith(".effectivealtruism.org")):
                raise ValueError(f"Unsafe redirect domain: {netloc}")

            current_url = redirect_url
        else:
            break
    else:
        raise requests.TooManyRedirects(f"Exceeded maximum redirects for {url}")

    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def is_ea_forum_post(url: str) -> bool:
    """Check whether a URL points to an EA Forum post or sequence.

    Args:
        url: Absolute or relative URL to test.

    Returns:
        ``True`` if the URL matches a known EA Forum post pattern.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", ""):
        return False
    return parsed.netloc in ("forum.effectivealtruism.org", "") and ("/posts/" in parsed.path or "/s/" in parsed.path)


def html_to_markdown(html_element: Tag) -> str:
    """Convert a BeautifulSoup element to clean markdown.

    Navigation, footer, script, style, and comment sections are stripped
    before conversion to avoid including non-content material.

    Args:
        html_element: BeautifulSoup ``Tag`` containing the HTML to convert.

    Returns:
        Cleaned markdown string.
    """
    # Remove navigation, footer, and other non-content elements
    for element in html_element.find_all(["nav", "footer", "script", "style", "noscript"]):
        element.decompose()
    # Remove comment sections so forum debates are not included
    for element in html_element.find_all(
        "div",
        class_=lambda c: c and "comments" in c.lower(),
    ):
        element.decompose()
    return markdownify(str(html_element), heading_style="ATX").strip()


def extract_author(soup: BeautifulSoup) -> str:
    """Extract the author name from a post page, trying several strategies.

    Strategies tried in order: JSON-LD structured data, ``<meta>`` author
    tag, common byline class patterns.

    Args:
        soup: Parsed post page.

    Returns:
        Author name, or an empty string if none could be found.
    """
    name = extract_author_json_ld(soup)
    if name:
        return name

    name = extract_author_meta(soup)
    if name:
        return name

    return extract_author_byline(soup)


def extract_author_json_ld(soup: BeautifulSoup) -> str:
    """Try to extract author from JSON-LD structured data.

    Args:
        soup: Parsed page containing potential ``<script type="application/ld+json">`` blocks.

    Returns:
        Author name, or an empty string if not found.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError, TypeError:
            continue
        if not isinstance(data, dict):
            continue
        author = data.get("author")
        if isinstance(author, dict):
            name = author.get("name", "")
            if name:
                return name
        elif isinstance(author, str) and author:
            return author
    return ""


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

    Searches for ``<a>``, ``<span>``, or ``<div>`` elements whose CSS
    class contains ``author``, ``byline``, ``username``, or ``UsersName``.

    Args:
        soup: Parsed page.

    Returns:
        Author name, or an empty string if not found.
    """
    for class_pattern in ("author", "byline", "username", "UsersName"):
        pattern_lower = class_pattern.lower()
        tag = soup.find(
            lambda t, p=pattern_lower: (
                t.name in ("a", "span", "div") and t.get("class") and any(p in c.lower() for c in t["class"])
            ),
        )
        if tag:
            text = tag.get_text(strip=True)
            if text:
                return text
    return ""


def extract_date(soup: BeautifulSoup) -> str:
    """Extract the publication date from a post page.

    Tries JSON-LD, ``<meta>`` date properties, and ``<time>`` elements
    in that order.

    Args:
        soup: Parsed post page.

    Returns:
        ISO date string (YYYY-MM-DD), or an empty string if not found.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                for key in ("datePublished", "dateCreated"):
                    date_str = data.get(key, "")
                    if date_str:
                        return date_str[:10]  # YYYY-MM-DD
        except json.JSONDecodeError, TypeError:
            continue

    for attr_name in ("article:published_time", "datePublished", "date"):
        meta = soup.find("meta", attrs={"property": attr_name}) or soup.find(
            "meta",
            attrs={"name": attr_name},
        )
        if meta and meta.get("content"):
            return str(meta["content"]).strip()[:10]

    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return str(time_tag["datetime"])[:10]

    return ""


def find_largest_content_division(soup: BeautifulSoup) -> Tag | None:
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
    div_text_lengths: dict[int, int] = {}
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, Comment):
            continue
        length = len(text_node)
        if length == 0:
            continue
        parent = text_node.parent
        while parent is not None:
            if parent.name == "div":
                div_id = id(parent)
                div_text_lengths[div_id] = div_text_lengths.get(div_id, 0) + length
            parent = parent.parent
    if not div_text_lengths:
        return None
    return max(divisions, key=lambda d: div_text_lengths.get(id(d), 0))


def _extract_from_react_structure(content: Tag) -> list[Post]:
    posts: list[Post] = []
    items = content.find_all("div", class_=lambda c: c and "LargeSequencesItem-columns" in c)
    for item in items:
        title_tag = item.find("div", class_=lambda c: c and "LargeSequencesItem-titleAndAuthor" in c)
        current_section = "Introduction"
        if title_tag:
            a_tag = title_tag.find("a")
            current_section = a_tag.get_text(strip=True) if a_tag else title_tag.get_text(strip=True)

        right = item.find("div", class_=lambda c: c and "LargeSequencesItem-right" in c)
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


def scrape_handbook_index(session: requests.Session | None = None) -> list[Post]:
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
    content = soup.find("div", class_=lambda c: c and "content" in c.lower() and "tableofcontents" not in c.lower())
    if content is None:
        content = soup.find("main") or soup.find("article") or soup.body

    # If we notice LargeSequencesItem anywhere in the body, prefer the full body to avoid missing them
    if soup.find("div", class_=lambda c: c and "LargeSequencesItem-columns" in c):
        content = soup.body

    if content is None:
        return []

    posts = extract_posts_from_content(content)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_posts: list[Post] = []
    for post in posts:
        if post.url not in seen:
            seen.add(post.url)
            unique_posts.append(post)

    return unique_posts


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
    return (
        soup.find("div", class_=lambda c: c and "postBody" in c)
        or soup.find("div", class_=lambda c: c and "post-body" in c)
        or soup.find("div", class_=lambda c: c and "PostBody" in c)
        or soup.find("div", {"itemprop": "articleBody"})
        or soup.find("article")
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

    post.author = extract_author(soup)
    post.posted_date = extract_date(soup)

    return post




def _read_cache(cache_path: Path, post: Post) -> bool:
    if not cache_path.exists():
        return False
    try:
        with cache_path.open(encoding="utf-8") as f:
            data = json.load(f)
            post.markdown = data.get("markdown", "")
            post.author = data.get("author", "")
            post.posted_date = data.get("posted_date", "")
    except (json.JSONDecodeError, OSError):
        return False
    else:
        return True

def _write_cache(cache_path: Path, post: Post) -> None:
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

def scrape_all(
    session: requests.Session | None = None,
    delay: float = REQUEST_DELAY,
    verbose: bool = False,
    cache_dir: Path | None = None,
) -> Handbook:
    """Scrape the full handbook: index + all post contents.

    Args:
        session: Optional requests session (useful for testing with mocks).
        delay: Seconds to wait between requests (be polite to the server).
        verbose: Emit progress messages via ``click.echo``.
        cache_dir: Optional directory to cache downloaded posts.

    Returns:
        A ``Handbook`` containing every post with content populated.
    """
    if session is None:
        session = make_session()

    if verbose:
        click.echo(f"Fetching handbook index from {HANDBOOK_URL} …")
    posts = scrape_handbook_index(session)

    if verbose:
        click.echo(f"Found {len(posts)} posts. Fetching content …")

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    handbook = Handbook(posts=posts)

    for i, post in enumerate(handbook.posts, 1):
        if verbose:
            click.echo(f"  [{i}/{len(posts)}] {post.title}")

        if cache_dir is not None:
            url_hash = hashlib.sha256(post.url.encode("utf-8")).hexdigest()[:16]
            cache_path = cache_dir / f"{url_hash}.json"
            if _read_cache(cache_path, post):
                continue

        scrape_post_content(post, session)

        if cache_dir is not None:
            _write_cache(cache_path, post)

        time.sleep(delay)

    return handbook
