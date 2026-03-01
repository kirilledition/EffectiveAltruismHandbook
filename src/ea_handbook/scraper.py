"""Scraper for the EA Handbook at forum.effectivealtruism.org/handbook."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify

HANDBOOK_URL = "https://forum.effectivealtruism.org/handbook"
BASE_URL = "https://forum.effectivealtruism.org"
REQUEST_DELAY = 1.0  # seconds between requests


@dataclass
class Post:
    """A single post/chapter from the EA Handbook."""

    title: str
    url: str
    section: str = ""
    markdown: str = ""


@dataclass
class Handbook:
    """The full EA Handbook with all posts."""

    posts: list[Post] = field(default_factory=list)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; EA-Handbook-Bot/1.0; "
                "+https://github.com/kirilledition/EffectiveAltruismHandbook)"
            )
        }
    )
    return session


def _fetch(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def _is_ea_forum_post(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in ("forum.effectivealtruism.org", "") and (
        "/posts/" in parsed.path or "/s/" in parsed.path
    )


def _html_to_markdown(html_element: Tag) -> str:
    """Convert a BeautifulSoup element to clean markdown."""
    # Remove navigation, footer, and other non-content elements
    for tag in html_element.find_all(
        ["nav", "footer", "script", "style", "noscript"]
    ):
        tag.decompose()
    # Remove comment sections so forum debates are not included
    for tag in html_element.find_all(
        "div", class_=lambda c: c and "comments" in c.lower()
    ):
        tag.decompose()
    return markdownify(str(html_element), heading_style="ATX").strip()


def scrape_handbook_index(session: Optional[requests.Session] = None) -> list[Post]:
    """
    Fetch the handbook index and return a list of Posts with title/url/section.
    Content is not yet fetched at this stage.
    """
    if session is None:
        session = _make_session()

    soup = _fetch(session, HANDBOOK_URL)
    posts: list[Post] = []

    # The handbook page contains a table of contents with sections and links.
    # Sections are typically <h2> or <h3> headings followed by lists of links.
    current_section = "Introduction"

    # Look for the main content area
    content = soup.find("div", class_=lambda c: c and "content" in c.lower())
    if content is None:
        content = soup.find("main") or soup.find("article") or soup.body

    if content is None:
        return posts

    for element in content.find_all(["h1", "h2", "h3", "ul"]):
        tag = element.name
        if tag in ("h1", "h2", "h3"):
            current_section = element.get_text(strip=True)
        elif tag == "ul":
            for link in element.find_all("a", recursive=True):
                href = link.get("href", "")
                if not href:
                    continue
                url = urljoin(BASE_URL, href) if not href.startswith("http") else href
                if _is_ea_forum_post(url):
                    title = link.get_text(strip=True)
                    if title:
                        posts.append(Post(title=title, url=url, section=current_section))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_posts: list[Post] = []
    for post in posts:
        if post.url not in seen:
            seen.add(post.url)
            unique_posts.append(post)

    return unique_posts


def scrape_post_content(post: Post, session: Optional[requests.Session] = None) -> Post:
    """Fetch the content of a single post and populate its markdown field."""
    if session is None:
        session = _make_session()

    soup = _fetch(session, post.url)

    # Try to find the post body – EA Forum uses various class patterns
    body = (
        soup.find("div", class_=lambda c: c and "postBody" in c)
        or soup.find("div", class_=lambda c: c and "post-body" in c)
        or soup.find("div", class_=lambda c: c and "PostBody" in c)
        or soup.find("div", {"itemprop": "articleBody"})
        or soup.find("article")
    )

    if body is None:
        # Fallback: grab the largest <div> that looks like content
        divs = soup.find_all("div")
        if divs:
            from bs4.element import Comment
            div_text_lengths = {}
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
            if div_text_lengths:
                body = max(divs, key=lambda d: div_text_lengths.get(id(d), 0))
            else:
                body = None

    if body:
        post.markdown = _html_to_markdown(body)
    else:
        post.markdown = f"*Content could not be extracted from {post.url}*"

    return post


def scrape_all(
    session: Optional[requests.Session] = None,
    delay: float = REQUEST_DELAY,
    verbose: bool = False,
) -> Handbook:
    """
    Scrape the full handbook: index + all post contents.

    Parameters
    ----------
    session:
        Optional requests session (useful for testing with mocks).
    delay:
        Seconds to wait between requests (be polite to the server).
    verbose:
        Print progress information.
    """
    if session is None:
        session = _make_session()

    if verbose:
        print(f"Fetching handbook index from {HANDBOOK_URL} …")
    posts = scrape_handbook_index(session)

    if verbose:
        print(f"Found {len(posts)} posts. Fetching content …")

    handbook = Handbook(posts=posts)

    for i, post in enumerate(handbook.posts, 1):
        if verbose:
            print(f"  [{i}/{len(posts)}] {post.title}")
        scrape_post_content(post, session)
        time.sleep(delay)

    return handbook
