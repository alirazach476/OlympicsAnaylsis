"""Wikipedia URL normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse, urlunparse

WIKI_HOSTS = {"en.wikipedia.org", "www.wikipedia.org"}
ARTICLE_PREFIX = "/wiki/"
DISALLOWED_PREFIXES = (
    "File:",
    "Image:",
    "Category:",
    "Help:",
    "Wikipedia:",
    "Template:",
    "Portal:",
    "Draft:",
    "Module:",
    "MediaWiki:",
    "Special:",
    "Talk:",
    "User:",
    "User_talk:",
    "Wikipedia_talk:",
    "File_talk:",
    "Template_talk:",
    "Category_talk:",
    "Help_talk:",
    "Portal_talk:",
)


def title_from_url(url: str) -> str:
    path = urlparse(url).path
    if "/wiki/" in path:
        raw = path.split("/wiki/", 1)[1]
        return unquote(raw.replace("_", " "))
    return unquote(path.strip("/").replace("_", " "))


def title_to_url(title: str) -> str:
    slug = title.replace(" ", "_")
    return f"https://en.wikipedia.org/wiki/{quote(slug, safe=':()/,_#%-')}"


def normalize_wikipedia_url(url: str) -> str | None:
    """Normalize to canonical en.wikipedia.org/wiki/Title without fragment or query.

    Returns None if the URL is not an English Wikipedia article URL.
    """
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/wiki/"):
        url = "https://en.wikipedia.org" + url

    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host and host not in WIKI_HOSTS and not host.endswith(".wikipedia.org"):
        return None
    if host.endswith(".wikipedia.org") and not host.startswith("en."):
        # Restrict crawl to English Wikipedia for this phase.
        if host != "en.wikipedia.org":
            return None

    path = parsed.path or ""
    if not path.startswith(ARTICLE_PREFIX):
        return None

    title_part = path[len(ARTICLE_PREFIX) :]
    if not title_part or title_part.startswith("Special:"):
        return None

    decoded = unquote(title_part)
    for prefix in DISALLOWED_PREFIXES:
        if decoded.startswith(prefix) or decoded.startswith(prefix.replace("_", " ")):
            return None

    # Drop section fragments and query strings.
    canonical_title = decoded.replace(" ", "_")
    # Collapse duplicate underscores / trailing slash
    canonical_title = re.sub(r"_+", "_", canonical_title).strip("_")
    return f"https://en.wikipedia.org/wiki/{canonical_title}"


def is_article_title_allowed(title: str) -> bool:
    for prefix in DISALLOWED_PREFIXES:
        clean = prefix.rstrip(":")
        if title.startswith(prefix) or title.startswith(clean + ":"):
            return False
    return True
