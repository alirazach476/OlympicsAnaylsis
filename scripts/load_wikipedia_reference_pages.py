#!/usr/bin/env python3
"""Load two Wikipedia reference pages from cached HTML (idempotent, offline):

wikipedia_stripped_medals <- "List of stripped Olympic medals" (main list + the "later returned" list)
wikipedia_ioc_country_codes <- "List of IOC country codes" (current NOCs, codes still in use, obsolete codes,
special codes for the Olympics). NPC/Paralympic/World-Games tables on that page are not Olympics data and are skipped.

Raw HTML is cached at data/raw/wikipedia/reference/*.html (fetched once via MediaWikiClient, which has its own
request cache). Nothing is invented; cells are stored as the page renders them.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "data" / "raw" / "wikipedia" / "reference"
DB_PATH = ROOT / "data" / "olympics_warehouse.db"

STRIPPED_URL = "https://en.wikipedia.org/wiki/List_of_stripped_Olympic_medals"
IOC_CODES_URL = "https://en.wikipedia.org/wiki/List_of_IOC_country_codes"


def fetch_cached(title: str, filename: str) -> str:
    path = REF_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    from backend.scrapers.wikipedia.mediawiki import MediaWikiClient

    html = MediaWikiClient().get_html(title)
    REF_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return html


def medal_from_cell(td) -> str | None:
    img = td.find("img")
    if img and img.get("alt"):
        alt = img["alt"].lower()
        if "gold" in alt:
            return "Gold"
        if "silver" in alt:
            return "Silver"
        if "bronze" in alt:
            return "Bronze"
    text = td.get_text(strip=True)
    return text or None


def parse_rowspan_table(table, returned: bool) -> list[dict]:
    """Parse a wikitable with rowspan'd Olympics/Athlete/Country cells into one row per event."""
    rows = table.find_all("tr")
    carry: dict[int, tuple[str | None, int]] = {}
    out = []
    for tr in rows[1:]:
        cells = list(tr.find_all(["td", "th"]))
        idx = 0
        colpos = 0
        result: dict[int, str | None] = {}
        while colpos <= 4:
            if colpos in carry and carry[colpos][1] > 0:
                result[colpos] = carry[colpos][0]
                carry[colpos] = (carry[colpos][0], carry[colpos][1] - 1)
                colpos += 1
                continue
            if idx >= len(cells):
                break
            td = cells[idx]
            idx += 1
            rowspan = int(td.get("rowspan", 1))
            value = medal_from_cell(td) if colpos == 3 else td.get_text(" ", strip=True)
            result[colpos] = value
            if rowspan > 1:
                carry[colpos] = (value, rowspan - 1)
            colpos += 1
        if not result.get(0):
            continue
        out.append(
            {
                "olympics": result.get(0),
                "athlete": result.get(1),
                "country": result.get(2),
                "medal": result.get(3),
                "event": result.get(4),
                "returned": returned,
            }
        )
    return out


def split_olympics(label: str) -> tuple[int | None, str | None]:
    m = re.search(r"(\d{4})\s+(Summer|Winter)\s+Olympics", label or "")
    if not m:
        return None, None
    return int(m.group(1)), m.group(2).lower()


def load_stripped_medals(conn: sqlite3.Connection) -> int:
    html = fetch_cached("List of stripped Olympic medals", "list_of_stripped_olympic_medals.html")
    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.find_all("table", class_="wikitable")]
    heading_map = {}
    for t in tables:
        prev = t.find_previous(["h2", "h3"])
        heading_map[id(t)] = prev.get_text(strip=True) if prev else None

    main_table = next(t for t in tables if heading_map[id(t)] == "Stripped medals")
    returned_table = next(
        t for t in tables if heading_map[id(t)] == "List of Olympic medals stripped and later returned"
    )

    rows = parse_rowspan_table(main_table, returned=False) + parse_rowspan_table(returned_table, returned=True)

    conn.executescript(
        """
        DROP TABLE IF EXISTS wikipedia_stripped_medals;
        CREATE TABLE wikipedia_stripped_medals(
            stripped_medal_id INTEGER PRIMARY KEY,
            olympics TEXT,
            year INTEGER,
            season TEXT,
            athlete TEXT,
            country TEXT,
            medal TEXT,
            event TEXT,
            returned INTEGER NOT NULL DEFAULT 0,
            source_url TEXT
        );
        """
    )
    values = []
    for r in rows:
        year, season = split_olympics(r["olympics"])
        values.append(
            (
                r["olympics"],
                year,
                season,
                r["athlete"],
                r["country"],
                r["medal"],
                r["event"],
                1 if r["returned"] else 0,
                STRIPPED_URL,
            )
        )
    conn.executemany(
        """
        INSERT INTO wikipedia_stripped_medals
            (olympics, year, season, athlete, country, medal, event, returned, source_url)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        values,
    )
    return len(values)


IOC_CATEGORIES = {
    "Current NOCs": "current",
    "Codes still in use": "codes_still_in_use",
    "Obsolete codes": "obsolete",
    "Special codes for Olympics": "special_olympics",
}


def parse_simple_table(table) -> list[list[str]]:
    rows = table.find_all("tr")
    out = []
    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        out.append([c.get_text(" ", strip=True) for c in cells])
    return out


def load_ioc_country_codes(conn: sqlite3.Connection) -> int:
    html = fetch_cached("List of IOC country codes", "list_of_ioc_country_codes.html")
    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.find_all("table", class_="wikitable")]
    heading_map = {}
    for t in tables:
        prev = t.find_previous(["h2", "h3", "h4"])
        heading_map[id(t)] = prev.get_text(strip=True) if prev else None

    conn.executescript(
        """
        DROP TABLE IF EXISTS wikipedia_ioc_country_codes;
        CREATE TABLE wikipedia_ioc_country_codes(
            code_id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            code TEXT,
            name TEXT,
            other_codes TEXT,
            years TEXT,
            notes TEXT,
            source_url TEXT
        );
        """
    )

    total = 0
    for t in tables:
        heading = heading_map[id(t)]
        category = IOC_CATEGORIES.get(heading)
        if not category:
            continue
        for row in parse_simple_table(t):
            if not row or not row[0]:
                continue
            code = row[0]
            if category in ("current", "codes_still_in_use"):
                name = row[1] if len(row) > 1 else None
                other = row[2] if len(row) > 2 else None
                years = None
                notes = None
            else:  # obsolete, special_olympics: Code, Nation, Years, Notes
                name = row[1] if len(row) > 1 else None
                years = row[2] if len(row) > 2 else None
                notes = row[3] if len(row) > 3 else None
                other = None
            conn.execute(
                """
                INSERT INTO wikipedia_ioc_country_codes
                    (category, code, name, other_codes, years, notes, source_url)
                VALUES (?,?,?,?,?,?,?)
                """,
                (category, code, name, other, years, notes, IOC_CODES_URL),
            )
            total += 1
    return total


def main() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=300)
    conn.execute("PRAGMA busy_timeout=300000")
    n1 = load_stripped_medals(conn)
    n2 = load_ioc_country_codes(conn)
    conn.commit()
    conn.close()
    print(f"wikipedia_stripped_medals: {n1} rows")
    print(f"wikipedia_ioc_country_codes: {n2} rows")


if __name__ == "__main__":
    main()
