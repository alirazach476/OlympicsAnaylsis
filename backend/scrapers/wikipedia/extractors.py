"""HTML structure extractors (tables, infobox, headings, references, links)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from backend.scrapers.wikipedia.urls import normalize_wikipedia_url, title_from_url


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.stripped_strings)


def extract_infobox(soup: BeautifulSoup) -> Dict[str, str]:
    infobox = soup.select_one("table.infobox")
    if not infobox:
        return {}
    data: Dict[str, str] = {}
    for row in infobox.select("tr"):
        header = row.find("th")
        value = row.find("td")
        if header and value:
            key = _cell_text(header)
            val = _cell_text(value)
            if key:
                data[key] = val
    return data


def extract_headings(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    headings = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        level = int(tag.name[1])
        text = _cell_text(tag)
        if text:
            headings.append({"level": level, "text": text, "id": tag.get("id")})
    return headings


def extract_tables(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    for idx, table in enumerate(soup.select("table.wikitable, table.sortable, table.infobox")):
        classes = table.get("class") or []
        if "infobox" in classes:
            # Infobox already extracted separately; skip duplicate as generic table.
            continue
        caption_tag = table.find("caption")
        caption = _cell_text(caption_tag) if caption_tag else None
        headers: List[str] = []
        header_row = table.select_one("tr")
        if header_row:
            headers = [_cell_text(c) for c in header_row.find_all(["th", "td"])]
        rows: List[List[str]] = []
        for row in table.select("tr")[1:]:
            cells = [_cell_text(c) for c in row.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        tables.append(
            {
                "index": idx,
                "caption": caption,
                "classes": list(classes),
                "headers": headers,
                "row_count": len(rows),
                "rows": rows[:500],  # cap oversized tables in DB-facing JSON
                "truncated": len(rows) > 500,
            }
        )
    return tables


def extract_references(soup: BeautifulSoup) -> List[Dict[str, str]]:
    refs = []
    for li in soup.select("ol.references li, div.reflist li"):
        ref_id = li.get("id")
        text = _cell_text(li)
        hrefs = [a.get("href") for a in li.select("a[href]") if a.get("href")]
        refs.append({"id": ref_id, "text": text[:1000], "links": hrefs[:20]})
        if len(refs) >= 300:
            break
    return refs


def extract_internal_links_from_html(soup: BeautifulSoup) -> List[Dict[str, str]]:
    content = soup.select_one("div.mw-parser-output") or soup
    found: List[Dict[str, str]] = []
    seen = set()
    for a in content.select("a[href]"):
        href = a.get("href") or ""
        if not href.startswith("/wiki/"):
            continue
        if ":" in href.split("/wiki/", 1)[-1] and not href.startswith("/wiki/List_"):
            # skip most namespace links; List_ articles are allowed via earlier filter
            title_part = href.split("/wiki/", 1)[-1]
            if any(
                title_part.startswith(p)
                for p in (
                    "File:",
                    "Category:",
                    "Help:",
                    "Wikipedia:",
                    "Template:",
                    "Special:",
                    "Talk:",
                    "User:",
                    "Portal:",
                    "Draft:",
                    "Module:",
                )
            ):
                continue
        norm = normalize_wikipedia_url(href)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        found.append(
            {
                "url": norm,
                "title": title_from_url(norm),
                "link_text": _cell_text(a)[:300],
            }
        )
    return found


def extract_images_from_html(soup: BeautifulSoup) -> List[Dict[str, str]]:
    images = []
    for img in soup.select("div.mw-parser-output img"):
        src = img.get("src") or ""
        alt = img.get("alt") or ""
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        images.append({"src": src, "alt": alt})
        if len(images) >= 100:
            break
    return images


def parse_html_bundle(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    return {
        "infobox": extract_infobox(soup),
        "headings": extract_headings(soup),
        "tables": extract_tables(soup),
        "references": extract_references(soup),
        "html_links": extract_internal_links_from_html(soup),
        "html_images": extract_images_from_html(soup),
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
