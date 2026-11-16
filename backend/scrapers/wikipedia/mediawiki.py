"""MediaWiki API client with etiquette: User-Agent, maxlag, backoff, caching."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import get_settings

logger = logging.getLogger(__name__)


class MediaWikiError(Exception):
    pass


class RateLimitedError(MediaWikiError):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class MediaWikiClient:
    """Conservative sequential MediaWiki client for en.wikipedia.org."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.settings.wiki_user_agent,
                "Accept": "application/json",
            }
        )
        self.api_url = self.settings.wiki_api_url
        self.cache_dir = Path(self.settings.wiki_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        delay = float(self.settings.wiki_request_delay_seconds)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def _cache_key(self, params: Dict[str, Any]) -> Path:
        raw = json.dumps(params, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, path: Path) -> Optional[Dict[str, Any]]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _write_cache(self, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @retry(
        retry=retry_if_exception_type((RateLimitedError, requests.RequestException)),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def _request(self, params: Dict[str, Any], *, use_cache: bool = True) -> Dict[str, Any]:
        params = {
            **params,
            "format": "json",
            "formatversion": 2,
            "maxlag": self.settings.wiki_maxlag_seconds,
        }
        cache_path = self._cache_key(params)
        if use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        self._throttle()
        self._last_request_at = time.monotonic()
        response = self.session.get(self.api_url, params=params, timeout=60)

        if response.status_code in (429, 503):
            retry_after = response.headers.get("Retry-After")
            wait_s = float(retry_after) if retry_after and retry_after.isdigit() else None
            if wait_s:
                time.sleep(wait_s)
            raise RateLimitedError(
                f"HTTP {response.status_code} from MediaWiki", retry_after=wait_s
            )

        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            code = err.get("code")
            if code == "maxlag":
                raise RateLimitedError(err.get("info", "maxlag"), retry_after=5)
            raise MediaWikiError(f"MediaWiki API error: {err}")

        if use_cache:
            self._write_cache(cache_path, data)
        return data

    def _continue_all(self, params: Dict[str, Any], result_key: str) -> List[Any]:
        """Follow continuation tokens until exhausted."""
        collected: List[Any] = []
        cont: Dict[str, Any] = {}
        while True:
            merged = {**params, **cont}
            data = self._request(merged, use_cache=True)
            query = data.get("query", {})
            chunk = query.get(result_key, [])
            if isinstance(chunk, dict):
                # pages keyed by id
                collected.extend(chunk.values() if not isinstance(next(iter(chunk.values()), None), dict) else chunk.values())
            else:
                collected.extend(chunk)

            # Also handle pages dict form
            if result_key == "pages" and "pages" in query:
                pages = query["pages"]
                if isinstance(pages, list):
                    collected = pages if not cont else collected + [
                        p for p in pages if p not in collected
                    ]
                elif isinstance(pages, dict):
                    collected = list(pages.values())

            if "continue" in data:
                cont = data["continue"]
            else:
                break
        return collected

    def get_page_bundle(self, title: str) -> Dict[str, Any]:
        """Fetch page info, extract, categories, images, revisions in one query (+continues)."""
        logger.info("MediaWiki page bundle: %s", title)
        params = {
            "action": "query",
            "titles": title,
            "prop": "info|extracts|categories|images|revisions|pageprops|pageimages",
            "inprop": "url|displaytitle",
            "exintro": 1,  # lead extract; full text via parse HTML when needed
            "explaintext": 1,
            "exsectionformat": "plain",
            "cllimit": "max",
            "imlimit": "max",
            "rvprop": "ids|timestamp|user",
            "rvlimit": 1,
            "piprop": "thumbnail|name|original",
            "pithumbsize": 400,
            "redirects": 1,
        }
        data = self._request(params)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return {}
        page = pages[0]
        if page.get("missing"):
            return {"missing": True, "title": title}

        # Continue categories / images if truncated (hard cap to avoid runaway loops)
        for _ in range(20):
            if "continue" not in data:
                break
            cont = data["continue"]
            data2 = self._request({**params, **cont})
            pages2 = data2.get("query", {}).get("pages", [])
            if pages2:
                p2 = pages2[0]
                page.setdefault("categories", []).extend(p2.get("categories", []))
                page.setdefault("images", []).extend(p2.get("images", []))
            data = data2

        return page

    def get_links(self, title: str, *, max_links: int = 2000) -> List[str]:
        """Return internal article link titles from a page (with continuation)."""
        logger.info("MediaWiki links: %s", title)
        params = {
            "action": "query",
            "titles": title,
            "prop": "links",
            "plnamespace": 0,
            "pllimit": "max",
            "redirects": 1,
        }
        titles: List[str] = []
        cont: Dict[str, Any] = {}
        for _ in range(30):
            data = self._request({**params, **cont})
            pages = data.get("query", {}).get("pages", [])
            if pages:
                for link in pages[0].get("links", []) or []:
                    t = link.get("title")
                    if t:
                        titles.append(t)
            if "continue" not in data or len(titles) >= max_links:
                break
            cont = data["continue"]
        # de-dupe preserve order
        seen = set()
        unique = []
        for t in titles:
            if t not in seen:
                seen.add(t)
                unique.append(t)
            if len(unique) >= max_links:
                break
        return unique

    def get_html(self, title: str) -> str:
        """Parse action HTML for table/infobox extraction."""
        logger.info("MediaWiki parse HTML: %s", title)
        params = {
            "action": "parse",
            "page": title,
            "prop": "text|sections|categories|images|externallinks|displaytitle",
            "disableeditsection": 1,
            "redirects": 1,
        }
        data = self._request(params)
        parse = data.get("parse", {})
        text = parse.get("text", "")
        if isinstance(text, dict):
            return text.get("*", "") or ""
        return text or ""

    def get_image_info(self, filenames: Iterable[str]) -> List[Dict[str, Any]]:
        """Resolve Commons/Wikipedia file metadata for a list of File: titles."""
        results: List[Dict[str, Any]] = []
        batch: List[str] = []
        for name in filenames:
            batch.append(name if name.startswith("File:") else f"File:{name}")
            if len(batch) >= 40:
                results.extend(self._image_info_batch(batch))
                batch = []
        if batch:
            results.extend(self._image_info_batch(batch))
        return results

    def _image_info_batch(self, titles: List[str]) -> List[Dict[str, Any]]:
        params = {
            "action": "query",
            "titles": "|".join(titles),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata|user|timestamp",
            "iiurlwidth": 640,
        }
        data = self._request(params)
        pages = data.get("query", {}).get("pages", [])
        out = []
        for page in pages:
            if page.get("missing"):
                continue
            info_list = page.get("imageinfo") or []
            info = info_list[0] if info_list else {}
            meta = info.get("extmetadata") or {}
            out.append(
                {
                    "title": page.get("title"),
                    "pageid": page.get("pageid"),
                    "url": info.get("url"),
                    "thumburl": info.get("thumburl"),
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "mime": info.get("mime"),
                    "user": info.get("user"),
                    "license": (meta.get("LicenseShortName") or {}).get("value"),
                    "artist": (meta.get("Artist") or {}).get("value"),
                    "attribution": (meta.get("Attribution") or {}).get("value"),
                    "description": (meta.get("ImageDescription") or {}).get("value"),
                }
            )
        return out
