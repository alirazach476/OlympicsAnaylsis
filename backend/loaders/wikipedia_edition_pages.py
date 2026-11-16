"""Scrape each Olympic edition's main Wikipedia page and fill missing master data.

Sources: https://en.wikipedia.org/wiki/{year}_{Season}_Olympics
Extracts infobox + key tables (venues, sports, participating NOCs).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collectors.editions import OlympicEdition, all_editions
from backend.models.core import Game, HistoricalNOC, Sport, Venue
from backend.scrapers.wikipedia.extractors import parse_html_bundle
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient

logger = logging.getLogger(__name__)


def _parse_int(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d[\d,]*)", text.replace("\xa0", " "))
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _parse_athletes_breakdown(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return total, male, female from strings like '5,347 (4,734 men, 613 women)'."""
    total = _parse_int(text)
    male = female = None
    m = re.search(r"([\d,]+)\s*men", text or "", re.I)
    f = re.search(r"([\d,]+)\s*women", text or "", re.I)
    if m:
        male = int(m.group(1).replace(",", ""))
    if f:
        female = int(f.group(1).replace(",", ""))
    return total, male, female


def _parse_events_sports(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse '150 in 17 sports (23 disciplines)' -> events, sports, disciplines."""
    events = sports = disciplines = None
    m = re.search(
        r"([\d,]+)\s*(?:events?\s*)?(?:in\s+)?([\d,]+)\s*sports?(?:\s*\(([\d,]+)\s*disciplines?\))?",
        text or "",
        re.I,
    )
    if m:
        events = int(m.group(1).replace(",", ""))
        sports = int(m.group(2).replace(",", ""))
        if m.group(3):
            disciplines = int(m.group(3).replace(",", ""))
    else:
        events = _parse_int(text or "")
    return events, sports, disciplines


def _parse_date(text: str) -> Optional[date]:
    if not text:
        return None
    # Drop references like [1]
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Range "6–22 February 2026" -> take first for opening elsewhere
    try:
        return dateparser.parse(text, fuzzy=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def _split_location(text: str) -> Tuple[Optional[str], Optional[str]]:
    text = re.sub(r"\[[^\]]*\]", "", text or "")
    text = text.replace("\xa0", " ").strip(" ,")
    if "," in text:
        city, country = text.split(",", 1)
        return city.strip(), country.strip()
    return text or None, None


class WikipediaEditionPageLoader:
    def __init__(self, session: Session, client: Optional[MediaWikiClient] = None):
        self.session = session
        self.client = client or MediaWikiClient()

    def fetch_page(self, edition: OlympicEdition) -> Dict[str, Any]:
        title = edition.wikipedia_title
        page = self.client.get_page_bundle(title)
        html = self.client.get_html(title)
        parsed = parse_html_bundle(html)
        soup = BeautifulSoup(html, "lxml")

        raw_dir = Path("data/raw/wikipedia/edition_pages")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_html = raw_dir / f"{edition.games_id}.html"
        raw_json = raw_dir / f"{edition.games_id}.json"
        raw_html.write_text(html, encoding="utf-8")

        infobox = parsed.get("infobox") or {}
        venues = self._extract_venues(soup, edition)
        sports = self._extract_sports_list(soup, parsed)
        nocs = self._extract_participating_nocs(soup, parsed)

        payload = {
            "games_id": edition.games_id,
            "title": page.get("title") or title,
            "page_id": page.get("pageid"),
            "revision_id": (page.get("revisions") or [{}])[0].get("revid"),
            "url": edition.wikipedia_url,
            "summary": (page.get("extract") or "")[:2000],
            "infobox": infobox,
            "headings": parsed.get("headings") or [],
            "venues": venues,
            "sports": sports,
            "participating_nocs": nocs,
            "table_count": len(parsed.get("tables") or []),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "license": "CC BY-SA 4.0",
            "attribution": f"Wikipedia contributors — {edition.wikipedia_url}",
        }
        raw_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def _extract_venues(self, soup: BeautifulSoup, edition: OlympicEdition) -> List[dict]:
        venues: List[dict] = []
        season_title = "Summer" if edition.season == "summer" else "Winter"
        venues_article = f"Venues of the {edition.year} {season_title} Olympics"

        # Prefer dedicated venues article when linked / available
        try:
            vhtml = self.client.get_html(venues_article)
            vsoup = BeautifulSoup(vhtml, "lxml")
            venues.extend(self._venues_from_soup(vsoup, edition, source_title=venues_article))
        except Exception:  # noqa: BLE001
            logger.info("No dedicated venues page for %s", edition.games_id)

        if venues:
            return venues

        # Fallback: venues section on the edition page (lists or tables)
        for heading in soup.select("h2, h3"):
            title = heading.get_text(" ", strip=True).lower()
            if "venue" not in title:
                continue
            container = heading.parent if heading.parent and heading.parent.name == "div" else heading
            for sib in container.next_siblings:
                if getattr(sib, "name", None) == "div" and "mw-heading2" in (sib.get("class") or []):
                    break
                if getattr(sib, "name", None) == "table" and "wikitable" in (sib.get("class") or []):
                    venues.extend(self._venues_from_table(sib, edition, edition.wikipedia_url))
                if getattr(sib, "name", None) == "ul":
                    for li in sib.select(":scope > li"):
                        a = li.find("a")
                        name = a.get_text(" ", strip=True) if a else li.get_text(" ", strip=True)
                        name = re.sub(r"\s+\d+$", "", name).strip()
                        sport = None
                        # text after emdash / colon often lists sports
                        txt = li.get_text(" ", strip=True)
                        if "–" in txt or "—" in txt or ":" in txt:
                            sport = re.split(r"[–—:]", txt, maxsplit=1)[-1].strip()[:200]
                        if name and len(name) > 1:
                            venues.append(
                                {
                                    "venue_name": name,
                                    "sport": sport,
                                    "capacity": None,
                                    "games_id": edition.games_id,
                                    "city": edition.host_city,
                                    "country": edition.host_country,
                                    "source_url": edition.wikipedia_url,
                                }
                            )
            if venues:
                break
        # de-dupe by name
        seen = set()
        uniq = []
        for v in venues:
            key = v["venue_name"].lower()
            if key in seen:
                continue
            seen.add(key)
            uniq.append(v)
        return uniq

    def _venues_from_soup(self, soup: BeautifulSoup, edition: OlympicEdition, source_title: str) -> List[dict]:
        url = f"https://en.wikipedia.org/wiki/{source_title.replace(' ', '_')}"
        out: List[dict] = []
        for table in soup.select("table.wikitable"):
            out.extend(self._venues_from_table(table, edition, url))
        return out

    def _venues_from_table(self, table, edition: OlympicEdition, source_url: str) -> List[dict]:
        headers = [th.get_text(" ", strip=True).lower() for th in table.select("tr th")]
        # Require a venue-like header
        if headers and not any(
            any(k in h for k in ("venue", "stadium", "arena", "location", "site"))
            for h in headers
        ):
            # still accept if first column looks like names and capacity/sport present
            if not any("capacity" in h or "sport" in h for h in headers):
                return []
        out: List[dict] = []
        name_i = 0
        for i, h in enumerate(headers):
            if any(k in h for k in ("venue", "stadium", "arena", "site")):
                name_i = i
                break
        sport_i = next((i for i, h in enumerate(headers) if "sport" in h or "event" in h), None)
        cap_i = next((i for i, h in enumerate(headers) if "capacity" in h), None)
        for tr in table.select("tr")[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if not cells or name_i >= len(cells):
                continue
            name = cells[name_i]
            if not name or len(name) < 2:
                continue
            out.append(
                {
                    "venue_name": name,
                    "sport": cells[sport_i] if sport_i is not None and sport_i < len(cells) else None,
                    "capacity": _parse_int(cells[cap_i]) if cap_i is not None and cap_i < len(cells) else None,
                    "games_id": edition.games_id,
                    "city": edition.host_city,
                    "country": edition.host_country,
                    "source_url": source_url,
                }
            )
        return out

    def _extract_sports_list(self, soup: BeautifulSoup, parsed: dict) -> List[str]:
        sports: List[str] = []
        for heading in soup.select("h2, h3"):
            if "sport" not in heading.get_text(" ", strip=True).lower():
                continue
            # Collect list items after heading
            for sib in heading.find_all_next(["ul", "div", "h2", "h3"], limit=20):
                if sib.name in {"h2", "h3"} and sib is not heading:
                    break
                if sib.name == "ul":
                    for li in sib.select(":scope > li"):
                        text = li.get_text(" ", strip=True)
                        # often "Athletics (24)" or linked sport name
                        name = re.split(r"\(|–|-", text)[0].strip()
                        if name and len(name) < 60:
                            sports.append(name)
                    if sports:
                        return sorted(set(sports))
        return sports

    def _extract_participating_nocs(self, soup: BeautifulSoup, parsed: dict) -> List[dict]:
        nocs: List[dict] = []
        for heading in soup.select("h2, h3"):
            t = heading.get_text(" ", strip=True).lower()
            if "participating" not in t and "national olympic" not in t:
                continue
            for sib in heading.find_all_next(["ul", "div", "table", "h2"], limit=30):
                if sib.name == "h2" and sib is not heading:
                    break
                if sib.name == "ul":
                    for li in sib.select(":scope > li"):
                        text = li.get_text(" ", strip=True)
                        m = re.match(r"(.+?)\s*\((\d+)\)\s*$", text)
                        if m:
                            nocs.append({"name": m.group(1).strip(), "athletes": int(m.group(2))})
                        elif text:
                            nocs.append({"name": re.split(r"\(", text)[0].strip(), "athletes": None})
                    if nocs:
                        return nocs
        return nocs

    def apply_to_game(self, edition: OlympicEdition, payload: Dict[str, Any]) -> Dict[str, Any]:
        game = self.session.get(Game, edition.games_id)
        if not game:
            game = Game(
                games_id=edition.games_id,
                year=edition.year,
                season=edition.season,
                official_edition_name=edition.official_edition_name,
            )
            self.session.add(game)

        box = payload.get("infobox") or {}
        updated = []

        loc = box.get("Location") or box.get("Host city") or ""
        city, country = _split_location(loc)
        if city and (not game.host_city or game.host_city != city):
            game.host_city = city
            updated.append("host_city")
        if country and not game.host_country:
            game.host_country = country
            updated.append("host_country")

        if box.get("Nations"):
            n = _parse_int(box["Nations"])
            if n:
                game.total_nocs = n
                updated.append("total_nocs")

        if box.get("Athletes"):
            total, male, female = _parse_athletes_breakdown(box["Athletes"])
            if total:
                game.total_athletes = total
                updated.append("total_athletes")
            if male is not None:
                game.male_athletes = male
                updated.append("male_athletes")
            if female is not None:
                game.female_athletes = female
                updated.append("female_athletes")

        events_txt = box.get("Events") or box.get("Event") or ""
        if events_txt:
            events, sports, disciplines = _parse_events_sports(events_txt)
            if events:
                game.total_events = events
                updated.append("total_events")
            if sports:
                game.total_sports = sports
                updated.append("total_sports")
            if disciplines:
                game.total_disciplines = disciplines
                updated.append("total_disciplines")

        opening = _parse_date(box.get("Opening") or box.get("Opening date") or "")
        closing = _parse_date(box.get("Closing") or box.get("Closing date") or "")
        if opening:
            game.opening_date = opening
            game.actual_event_start_date = opening
            updated.append("opening_date")
        if closing:
            game.closing_date = closing
            game.actual_event_end_date = closing
            updated.append("closing_date")

        stadium = box.get("Stadium") or box.get("Venue")
        # Store stadium as note via official_website unused? keep in source field blend
        game.wikipedia_url = edition.wikipedia_url
        game.source = "wikipedia_edition_page+athlete_events"
        game.verification_status = "partially_verified"
        updated.append("verification_status")

        # Venues upsert (by name+games)
        venue_added = 0
        for v in payload.get("venues") or []:
            existing = self.session.scalar(
                select(Venue).where(
                    Venue.games_id == edition.games_id,
                    Venue.venue_name == v["venue_name"],
                )
            )
            if existing:
                continue
            self.session.add(
                Venue(
                    games_id=edition.games_id,
                    venue_name=v["venue_name"],
                    city=v.get("city"),
                    country=v.get("country"),
                    sport=v.get("sport"),
                    capacity=v.get("capacity"),
                    source_url=v.get("source_url"),
                    verification_status="collected",
                )
            )
            venue_added += 1

        # Ensure sports names exist
        sports_added = 0
        for name in payload.get("sports") or []:
            exists = self.session.scalar(select(Sport).where(Sport.sport_name == name))
            if not exists:
                self.session.add(
                    Sport(
                        sport_name=name,
                        season=edition.season,
                        source_url=edition.wikipedia_url,
                        verification_status="collected",
                    )
                )
                sports_added += 1

        self.session.commit()
        return {
            "games_id": edition.games_id,
            "fields_updated": sorted(set(updated)),
            "venues_added": venue_added,
            "sports_added": sports_added,
            "nocs_listed": len(payload.get("participating_nocs") or []),
            "infobox_keys": list(box.keys()),
            "stadium": stadium,
        }

    def load_all(self, editions: Optional[List[OlympicEdition]] = None) -> dict:
        editions = editions or all_editions()
        results = []
        for edition in editions:
            logger.info("Edition page: %s (%s)", edition.games_id, edition.wikipedia_title)
            try:
                payload = self.fetch_page(edition)
                applied = self.apply_to_game(edition, payload)
                results.append({"ok": True, **applied})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed %s", edition.games_id)
                results.append({"ok": False, "games_id": edition.games_id, "error": str(exc)})
                self.session.rollback()

        summary = {
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "editions_ok": sum(1 for r in results if r.get("ok")),
            "editions_failed": [r for r in results if not r.get("ok")],
            "results": results,
        }
        out = Path("reports/scraping/wikipedia_edition_pages.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

        # Export enriched games
        import pandas as pd
        from sqlalchemy import create_engine
        from backend.config import get_settings

        engine = create_engine(get_settings().database_url)
        df = pd.read_sql(
            "select games_id, year, season, host_city, host_country, opening_date, closing_date, "
            "actual_event_start_date, actual_event_end_date, total_nocs, total_athletes, "
            "male_athletes, female_athletes, total_sports, total_disciplines, total_events, "
            "wikipedia_url, source, verification_status from games order by year, season",
            engine,
        )
        Path("data/exports").mkdir(parents=True, exist_ok=True)
        df.to_csv("data/exports/games_from_wikipedia.csv", index=False)
        return summary
