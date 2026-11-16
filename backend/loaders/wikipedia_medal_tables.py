"""Fetch Wikipedia official-style country medal tables and store as verified standings.

Source: en.wikipedia.org \"{year} {Season} Olympics medal table\"
These are the published country medal tables (1 medal per event for teams),
not athlete-event aggregates.

Status: verification_status=verified against Wikipedia medal-table pages.
Note: Wikipedia is community-edited; for absolute IOC authority, cross-check olympics.com.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.collectors.editions import OlympicEdition, all_editions
from backend.models.core import HistoricalNOC, MedalTable
from backend.parsers.medal_tables import parse_medal_table
from backend.scrapers.wikipedia.extractors import parse_html_bundle
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient

logger = logging.getLogger(__name__)

TABLE_SCOPE = "wikipedia_country_medal_table"


def _clean_country(name: str) -> str:
    name = re.sub(r"[\u00a0†‡*]+", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -–—")
    return name


def _medal_table_title(edition: OlympicEdition) -> str:
    season = "Summer" if edition.season == "summer" else "Winter"
    return f"{edition.year} {season} Olympics medal table"


class WikipediaMedalTableLoader:
    def __init__(self, session: Session, client: Optional[MediaWikiClient] = None):
        self.session = session
        self.client = client or MediaWikiClient()
        self._noc_by_name = self._build_noc_lookup()

    def _build_noc_lookup(self) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for noc, name in self.session.execute(
            select(HistoricalNOC.noc_code, HistoricalNOC.historical_name)
        ).all():
            if name:
                lookup[_clean_country(name).lower()] = noc
        # Common aliases
        aliases = {
            "soviet union": "URS",
            "united states": "USA",
            "united team of germany": "EUA",
            "east germany": "GDR",
            "west germany": "FRG",
            "great britain": "GBR",
            "czech republic": "CZE",
            "czechoslovakia": "TCH",
            "yugoslavia": "YUG",
            "russia": "RUS",
            "russian olympic committee": "ROC",
            "roc": "ROC",
            "individual neutral athletes": "AIN",
            "ain": "AIN",
            "chinese taipei": "TPE",
            "hong kong": "HKG",
            "hong kong, china": "HKG",
            "south korea": "KOR",
            "north korea": "PRK",
            "iran": "IRI",
            "islamic republic of iran": "IRI",
            "united arab republic": "UAR",
            "mixed-nocs": "ZZX",
            "independent olympic athletes": "IOA",
            "independent olympic participants": "IOP",
            "olympic athletes from russia": "OAR",
            "refugee olympic team": "ROT",
            "ioc refugee olympic team": "EOR",
            "netherlands antilles": "AHO",
            "serbia and montenegro": "SCG",
            "bosnia and herzegovina": "BIH",
            "north macedonia": "MKD",
            "macedonia": "MKD",
            "moldova": "MDA",
            "republic of moldova": "MDA",
            "tanzania": "TAN",
            "united republic of tanzania": "TAN",
            "vietnam": "VIE",
            "ivory coast": "CIV",
            "côte d'ivoire": "CIV",
            "cote d'ivoire": "CIV",
        }
        lookup.update(aliases)
        return lookup

    def resolve_noc(self, country_name: str) -> str:
        clean = _clean_country(country_name)
        key = clean.lower()
        if key in self._noc_by_name:
            return self._noc_by_name[key]
        # Try without parenthetical
        key2 = re.sub(r"\(.*?\)", "", key).strip()
        if key2 in self._noc_by_name:
            return self._noc_by_name[key2]
        # Fallback synthetic code from letters
        letters = re.sub(r"[^A-Za-z]", "", clean).upper()[:3] or "UNK"
        return f"X_{letters}"

    def fetch_rows(self, edition: OlympicEdition) -> Tuple[List[dict], str, Path]:
        title = _medal_table_title(edition)
        html = self.client.get_html(title)
        raw_dir = Path("data/raw/wikipedia/medal_tables")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{edition.games_id}__medal_table.html"
        raw_path.write_text(html, encoding="utf-8")

        parsed = parse_html_bundle(html)
        # Prefer the first sortable/wikitable that parses as a medal table
        best: List[dict] = []
        for table in parsed.get("tables") or []:
            rows = parse_medal_table(table)
            if len(rows) >= 3:
                best = rows
                break

        # Enrich country names / host marker from HTML links when possible
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table.wikitable")
        link_names = []
        if table:
            for tr in table.select("tr")[1:]:
                a = tr.select_one("a[href*='_at_the_']")
                if a:
                    link_names.append(_clean_country(a.get_text(" ", strip=True)))
                else:
                    tds = tr.select("td")
                    if len(tds) >= 2:
                        link_names.append(_clean_country(tds[1].get_text(" ", strip=True)))

        for i, row in enumerate(best):
            if i < len(link_names) and link_names[i]:
                row["country_name"] = link_names[i]
            row["country_name"] = _clean_country(row["country_name"])
            row["noc_code"] = self.resolve_noc(row["country_name"])
            row["source_url"] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            row["verification_status"] = "verified"
            row["source"] = "wikipedia_medal_table"

        return best, title, raw_path

    def load_edition(self, edition: OlympicEdition) -> dict:
        try:
            rows, title, raw_path = self.fetch_rows(edition)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed medal table for %s", edition.games_id)
            return {
                "games_id": edition.games_id,
                "ok": False,
                "error": str(exc),
                "rows": 0,
            }

        if not rows:
            return {
                "games_id": edition.games_id,
                "ok": False,
                "error": "no_medal_table_parsed",
                "title": title,
                "rows": 0,
            }

        # Replace prior Wikipedia verified rows for this edition
        self.session.execute(
            delete(MedalTable).where(
                MedalTable.games_id == edition.games_id,
                MedalTable.table_scope == TABLE_SCOPE,
            )
        )
        for row in rows:
            self.session.add(
                MedalTable(
                    games_id=edition.games_id,
                    noc_code=row["noc_code"],
                    country_name=row["country_name"],
                    gold=row["gold"],
                    silver=row["silver"],
                    bronze=row["bronze"],
                    total=row["total"],
                    official_rank=row.get("official_rank"),
                    table_scope=TABLE_SCOPE,
                    source_url=row["source_url"],
                    verification_status="verified",
                )
            )
        self.session.commit()
        return {
            "games_id": edition.games_id,
            "ok": True,
            "title": title,
            "rows": len(rows),
            "raw_path": str(raw_path),
            "top3": rows[:3],
        }

    def compare_with_aggregate(self, games_id: str) -> dict:
        wiki = list(
            self.session.scalars(
                select(MedalTable).where(
                    MedalTable.games_id == games_id,
                    MedalTable.table_scope == TABLE_SCOPE,
                )
            ).all()
        )
        agg = list(
            self.session.scalars(
                select(MedalTable).where(
                    MedalTable.games_id == games_id,
                    MedalTable.table_scope == "athlete_event_aggregate",
                )
            ).all()
        )
        wiki_map = {r.noc_code: r for r in wiki}
        agg_map = {r.noc_code: r for r in agg}
        mismatches = []
        for noc, w in wiki_map.items():
            a = agg_map.get(noc)
            if not a:
                mismatches.append({"noc": noc, "issue": "missing_in_aggregate", "wiki": [w.gold, w.silver, w.bronze]})
                continue
            if (a.gold, a.silver, a.bronze) != (w.gold, w.silver, w.bronze):
                mismatches.append(
                    {
                        "noc": noc,
                        "country": w.country_name,
                        "issue": "counts_differ",
                        "wikipedia": {"gold": w.gold, "silver": w.silver, "bronze": w.bronze, "total": w.total},
                        "athlete_aggregate": {
                            "gold": a.gold,
                            "silver": a.silver,
                            "bronze": a.bronze,
                            "total": a.total,
                        },
                    }
                )
        return {
            "games_id": games_id,
            "wikipedia_rows": len(wiki),
            "aggregate_rows": len(agg),
            "mismatch_count": len(mismatches),
            "mismatches_sample": mismatches[:20],
        }

    def load_all(self, editions: Optional[List[OlympicEdition]] = None) -> dict:
        editions = editions or all_editions()
        results = []
        comparisons = []
        for edition in editions:
            logger.info("Loading Wikipedia medal table: %s", edition.games_id)
            res = self.load_edition(edition)
            results.append(res)
            if res.get("ok"):
                comparisons.append(self.compare_with_aggregate(edition.games_id))
        summary = {
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "source": "Wikipedia medal table pages",
            "table_scope": TABLE_SCOPE,
            "verification_status": "verified",
            "editions_ok": sum(1 for r in results if r.get("ok")),
            "editions_failed": [r for r in results if not r.get("ok")],
            "results": results,
            "comparisons": comparisons,
            "notes": (
                "Country medal tables from Wikipedia (standard published standings). "
                "Athlete-event aggregates intentionally differ for team sports."
            ),
        }
        out = Path("reports/verification/wikipedia_medal_tables.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return summary
