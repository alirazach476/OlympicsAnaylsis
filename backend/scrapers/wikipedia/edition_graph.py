"""Extract calendar, sport links, country links from edition main pages; follow sport→event links."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collectors.editions import OlympicEdition, all_editions
from backend.models.core import Event, Sport
from backend.scrapers.wikipedia.extractors import parse_html_bundle
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient
from backend.scrapers.wikipedia.urls import normalize_wikipedia_url, title_from_url, title_to_url

logger = logging.getLogger(__name__)


def _edition_phrase(edition: OlympicEdition) -> str:
    season = "Summer" if edition.season == "summer" else "Winter"
    return f"{edition.year} {season} Olympics"


class EditionGraphScraper:
    def __init__(self, session: Session, client: Optional[MediaWikiClient] = None):
        self.session = session
        self.client = client or MediaWikiClient()
        self.raw_root = Path("data/raw/wikipedia/edition_graph")
        self.raw_root.mkdir(parents=True, exist_ok=True)

    def extract_from_edition_html(self, html: str, edition: OlympicEdition) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        phrase = _edition_phrase(edition)
        sports = self._section_links(soup, ("sport",), phrase, require_at_the=True)
        countries = self._section_links(
            soup,
            ("participating", "national olympic"),
            phrase,
            require_at_the=True,
            country_pattern=True,
        )
        # Also catch country links from medal table section
        if not countries:
            countries = self._all_at_the_links(soup, phrase, kind="country")
        calendar = self._extract_calendar(soup)
        return {
            "games_id": edition.games_id,
            "sports_links": sports,
            "country_links": countries,
            "calendar": calendar,
        }

    def _section_links(
        self,
        soup: BeautifulSoup,
        heading_keys: tuple,
        phrase: str,
        *,
        require_at_the: bool,
        country_pattern: bool = False,
    ) -> List[dict]:
        found: List[dict] = []
        seen: Set[str] = set()
        for heading in soup.select("h2, h3"):
            ht = heading.get_text(" ", strip=True).lower()
            if not any(k in ht for k in heading_keys):
                continue
            container = heading.parent if heading.parent and heading.parent.name == "div" else heading
            for a in container.find_all_next("a", href=True):
                # stop at next h2 block
                parent_h = a.find_parent("div", class_=re.compile("mw-heading"))
                if parent_h and parent_h != container and "mw-heading2" in (parent_h.get("class") or []):
                    # only stop if we've moved past and hit another h2 heading after start
                    h2 = parent_h.find("h2")
                    if h2 and h2 is not heading:
                        break
                href = a["href"]
                if not href.startswith("/wiki/"):
                    continue
                title = unquote(href.split("/wiki/", 1)[-1].replace("_", " "))
                if title.startswith(("File:", "Category:", "Help:", "Template:", "Special:", "Talk:")):
                    continue
                if require_at_the and f"at the {phrase}" not in title:
                    # sport pages are "Athletics at the 1960 Summer Olympics"
                    continue
                if country_pattern and not re.match(
                    rf"^.+ at the {re.escape(phrase)}$", title, re.I
                ):
                    # exclude sport pages which also match "at the"
                    # country pages: "{Country} at the YEAR Season Olympics"
                    # sport pages: "{Sport} at the ..." — hard to distinguish; country usually no sport keywords
                    first = title.split(" at the ")[0].strip().lower()
                    if first in {
                        "athletics", "swimming", "football", "basketball", "boxing",
                        "cycling", "fencing", "gymnastics", "hockey", "field hockey",
                        "rowing", "sailing", "shooting", "wrestling", "weightlifting",
                        "diving", "water polo", "equestrian", "canoeing", "modern pentathlon",
                        "volleyball", "handball", "tennis", "table tennis", "badminton",
                        "archery", "judo", "taekwondo", "triathlon", "golf", "rugby",
                        "rugby sevens", "baseball", "softball", "skateboarding", "surfing",
                        "sport climbing", "breaking", "karate",
                    }:
                        continue
                norm = normalize_wikipedia_url(href)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                found.append(
                    {
                        "title": title,
                        "url": norm,
                        "link_text": a.get_text(" ", strip=True),
                    }
                )
            if found:
                break
        return found

    def _all_at_the_links(self, soup: BeautifulSoup, phrase: str, kind: str) -> List[dict]:
        out = []
        seen = set()
        for a in soup.select("div.mw-parser-output a[href^='/wiki/']"):
            title = unquote(a["href"].split("/wiki/", 1)[-1].replace("_", " "))
            if f"at the {phrase}" not in title:
                continue
            left = title.split(" at the ")[0].strip()
            if kind == "country" and left.lower() in {"athletics", "football", "swimming"}:
                continue
            norm = normalize_wikipedia_url(a["href"])
            if not norm or norm in seen:
                continue
            seen.add(norm)
            out.append({"title": title, "url": norm, "link_text": a.get_text(" ", strip=True)})
        return out

    def _extract_calendar(self, soup: BeautifulSoup) -> Dict[str, Any]:
        for heading in soup.select("h2, h3"):
            if "calendar" not in heading.get_text(" ", strip=True).lower():
                continue
            container = heading.parent if heading.parent and heading.parent.name == "div" else heading
            for sib in container.next_siblings:
                if getattr(sib, "name", None) == "div" and "mw-heading2" in (sib.get("class") or []):
                    break
                if getattr(sib, "name", None) == "table":
                    headers = [th.get_text(" ", strip=True) for th in sib.select("tr th")]
                    rows = []
                    for tr in sib.select("tr")[1:]:
                        cells = [td.get_text(" ", strip=True) for td in tr.select("td,th")]
                        if cells:
                            rows.append(cells)
                    return {"headers": headers, "rows": rows[:200], "row_count": len(rows)}
        return {}

    def follow_sport_events(self, sport_title: str, edition: OlympicEdition) -> Dict[str, Any]:
        """Open a sport page and collect event sublinks + tables."""
        html = self.client.get_html(sport_title)
        parsed = parse_html_bundle(html)
        soup = BeautifulSoup(html, "lxml")
        phrase = _edition_phrase(edition)
        event_links = []
        seen = set()
        sport_root = sport_title.split(" at the ")[0].strip()
        for a in soup.select("div.mw-parser-output a[href^='/wiki/']"):
            title = unquote(a["href"].split("/wiki/", 1)[-1].replace("_", " "))
            # Event pages: "Athletics at the 1960 Summer Olympics – Men's 100 metres"
            if f"at the {phrase}" not in title:
                continue
            # Must be under this sport, with an event suffix after an en/em/hyphen dash
            if not title.lower().startswith(sport_root.lower()):
                continue
            if not re.search(r"[–—\-]", title.split(phrase, 1)[-1]):
                continue
            # Exclude pure nation pages and medal tables
            if re.match(rf"^.+ at the {re.escape(phrase)}$", title) and not re.search(
                r"[–—]", title
            ):
                continue
            if "medal table" in title.lower():
                continue
            norm = normalize_wikipedia_url(a["href"])
            if not norm or norm in seen:
                continue
            seen.add(norm)
            event_links.append(
                {
                    "title": title,
                    "url": norm,
                    "link_text": a.get_text(" ", strip=True),
                }
            )

        # Persist sport raw
        safe = re.sub(r"[^\w\-]+", "_", sport_title)[:120]
        out_dir = self.raw_root / edition.games_id / "sports"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{safe}.html").write_text(html, encoding="utf-8")
        payload = {
            "sport_title": sport_title,
            "games_id": edition.games_id,
            "event_links": event_links,
            "tables": parsed.get("tables") or [],
            "headings": parsed.get("headings") or [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        (out_dir / f"{safe}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

        # Ensure sport + event rows
        sport_name = sport_title.split(" at the ")[0].strip()
        sport = self.session.scalar(select(Sport).where(Sport.sport_name == sport_name))
        if not sport:
            sport = Sport(
                sport_name=sport_name,
                season=edition.season,
                source_url=title_to_url(sport_title),
                verification_status="collected",
            )
            self.session.add(sport)
            self.session.flush()

        events_added = 0
        for ev in event_links:
            # Use full title as event_name for uniqueness
            exists = self.session.scalar(
                select(Event).where(
                    Event.games_id == edition.games_id,
                    Event.event_name == ev["title"],
                )
            )
            if exists:
                continue
            gender = None
            tl = ev["title"].lower()
            if "women" in tl:
                gender = "F"
            elif "men" in tl and "women" not in tl:
                gender = "M"
            elif "mixed" in tl:
                gender = "X"
            self.session.add(
                Event(
                    games_id=edition.games_id,
                    sport_id=sport.sport_id,
                    event_name=ev["title"],
                    event_gender=gender,
                    source_url=ev["url"],
                    verification_status="collected",
                )
            )
            events_added += 1
        self.session.commit()
        return {
            "sport": sport_name,
            "event_links": len(event_links),
            "events_added": events_added,
            "table_count": len(payload["tables"]),
        }

    def scrape_edition(
        self,
        edition: OlympicEdition,
        *,
        follow_sports: bool = True,
        max_sports: Optional[int] = None,
        fetch_event_pages: bool = False,
        max_event_pages: int = 40,
    ) -> Dict[str, Any]:
        # Prefer already-saved edition HTML
        html_path = Path(f"data/raw/wikipedia/edition_pages/{edition.games_id}.html")
        if html_path.exists():
            html = html_path.read_text(encoding="utf-8")
        else:
            html = self.client.get_html(edition.wikipedia_title)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")

        graph = self.extract_from_edition_html(html, edition)
        graph_path = self.raw_root / edition.games_id / "edition_graph.json"
        graph_path.parent.mkdir(parents=True, exist_ok=True)

        sport_results = []
        if follow_sports:
            sports = graph["sports_links"]
            if max_sports is not None:
                sports = sports[:max_sports]
            for s in sports:
                try:
                    sport_results.append(self.follow_sport_events(s["title"], edition))
                    if fetch_event_pages:
                        # optionally fetch first N event pages for tables
                        # loaded inside follow via event_links file; fetch separately below
                        pass
                except Exception as exc:  # noqa: BLE001
                    self.session.rollback()
                    logger.exception("Sport failed %s", s["title"])
                    sport_results.append({"sport": s["title"], "error": str(exc)})

        # Optionally fetch event page bodies (100m etc.)
        events_fetched = 0
        if fetch_event_pages:
            events_dir = self.raw_root / edition.games_id / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            for sres, slink in zip(sport_results, graph["sports_links"]):
                # re-read event links from saved json if available
                safe = re.sub(r"[^\w\-]+", "_", slink["title"])[:120]
                jp = self.raw_root / edition.games_id / "sports" / f"{safe}.json"
                if not jp.exists():
                    continue
                data = json.loads(jp.read_text(encoding="utf-8"))
                for ev in data.get("event_links", [])[: max_event_pages // max(len(graph["sports_links"]), 1)]:
                    if events_fetched >= max_event_pages:
                        break
                    try:
                        ehtml = self.client.get_html(ev["title"])
                        esafe = re.sub(r"[^\w\-]+", "_", ev["title"])[:140]
                        (events_dir / f"{esafe}.html").write_text(ehtml, encoding="utf-8")
                        eparsed = parse_html_bundle(ehtml)
                        (events_dir / f"{esafe}.json").write_text(
                            json.dumps(
                                {
                                    "title": ev["title"],
                                    "url": ev["url"],
                                    "tables": eparsed.get("tables"),
                                    "headings": eparsed.get("headings"),
                                    "infobox": eparsed.get("infobox"),
                                },
                                indent=2,
                                ensure_ascii=False,
                                default=str,
                            ),
                            encoding="utf-8",
                        )
                        events_fetched += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Event page failed %s: %s", ev["title"], exc)

        # Save + fetch participating country pages
        countries_dir = self.raw_root / edition.games_id / "countries"
        countries_dir.mkdir(parents=True, exist_ok=True)
        (countries_dir / "links.json").write_text(
            json.dumps(graph["country_links"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        countries_fetched = 0
        for cl in graph["country_links"]:
            try:
                chtml = self.client.get_html(cl["title"])
                csafe = re.sub(r"[^\w\-]+", "_", cl["title"])[:140]
                (countries_dir / f"{csafe}.html").write_text(chtml, encoding="utf-8")
                cparsed = parse_html_bundle(chtml)
                (countries_dir / f"{csafe}.json").write_text(
                    json.dumps(
                        {
                            "title": cl["title"],
                            "url": cl["url"],
                            "infobox": cparsed.get("infobox"),
                            "tables": cparsed.get("tables"),
                            "headings": cparsed.get("headings"),
                        },
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    ),
                    encoding="utf-8",
                )
                countries_fetched += 1
            except Exception as exc:  # noqa: BLE001
                self.session.rollback()
                logger.warning("Country page failed %s: %s", cl["title"], exc)

        result = {
            **graph,
            "sports_count": len(graph["sports_links"]),
            "countries_count": len(graph["country_links"]),
            "calendar_rows": (graph.get("calendar") or {}).get("row_count", 0),
            "sport_results": sport_results,
            "event_pages_fetched": events_fetched,
            "countries_fetched": countries_fetched,
        }
        graph_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return result

    def scrape_all(self, **kwargs) -> dict:
        results = []
        for edition in all_editions():
            if edition.season != "summer" and kwargs.get("summer_only"):
                continue
            logger.info("Edition graph %s", edition.games_id)
            try:
                results.append({"ok": True, **self.scrape_edition(edition, **kwargs)})
            except Exception as exc:  # noqa: BLE001
                self.session.rollback()
                logger.exception(edition.games_id)
                results.append({"ok": False, "games_id": edition.games_id, "error": str(exc)})
        summary = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "editions_ok": sum(1 for r in results if r.get("ok")),
            "results": [
                {
                    "games_id": r.get("games_id"),
                    "ok": r.get("ok"),
                    "sports_count": r.get("sports_count"),
                    "countries_count": r.get("countries_count"),
                    "calendar_rows": r.get("calendar_rows"),
                    "event_pages_fetched": r.get("event_pages_fetched"),
                    "error": r.get("error"),
                }
                for r in results
            ],
        }
        Path("reports/scraping/edition_graph_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return summary
