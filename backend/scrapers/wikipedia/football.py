"""Deep-scrape Olympic football Wikipedia pages: matches, scores, squads."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collectors.editions import OlympicEdition, SUMMER_EDITIONS
from backend.models.core import Match, MatchResult, Sport, Team, TeamMember, Athlete
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient
from backend.scrapers.wikipedia.urls import normalize_wikipedia_url, title_to_url

logger = logging.getLogger(__name__)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _parse_date(text: str) -> Optional[date]:
    text = re.sub(r"\[[^\]]*\]", "", text or "")
    try:
        return dateparser.parse(text, fuzzy=True).date()
    except Exception:
        return None



SCORE_LINE = re.compile(
    r"(.+?)\s+(\d+)\s*[–\-—]\s*(\d+)\s+(.+?)(?:\s+Report|\s+Att|\s+Referee|\s+Stadio|\s+Stadium|$)"
)
SCORE_CELL = re.compile(r"(\d+)\s*[–\-—]\s*(\d+)")


def split_score_line(text: str):
    """'26 August 1960 17:00 Bulgaria 3-0 Turkey ...' -> ('26 August 1960 17:00 Bulgaria', '3', '0', 'Turkey').
    A colon is a clock separator, not a score separator: the old pattern read the kickoff time 17:00 as a 17-0 score."""
    m = SCORE_LINE.search(text)
    return (m.group(1), m.group(2), m.group(3), m.group(4)) if m else None

class FootballOlympicsScraper:
    def __init__(self, session: Session, client: Optional[MediaWikiClient] = None):
        self.session = session
        self.client = client or MediaWikiClient()
        self.raw_root = Path("data/raw/wikipedia/football")
        self.raw_root.mkdir(parents=True, exist_ok=True)

    def _ensure_sport(self) -> Sport:
        sport = self.session.scalar(select(Sport).where(Sport.sport_name == "Football"))
        if not sport:
            sport = Sport(sport_name="Football", season="summer", verification_status="collected")
            self.session.add(sport)
            self.session.flush()
        return sport

    def _ensure_team(self, games_id: str, sport_id: int, name: str, noc: Optional[str] = None) -> Team:
        name = _clean(name)
        existing = self.session.scalar(
            select(Team).where(
                Team.games_id == games_id,
                Team.sport_id == sport_id,
                Team.team_name == name,
            )
        )
        if existing:
            return existing
        team = Team(
            games_id=games_id,
            sport_id=sport_id,
            noc_code=noc,
            team_name=name,
            source_url=None,
            verification_status="collected",
        )
        self.session.add(team)
        self.session.flush()
        return team

    def discover_football_links(self, edition: OlympicEdition) -> List[str]:
        year = edition.year
        seeds = [
            f"Football at the {year} Summer Olympics",
            f"Football at the {year} Summer Olympics – Men's tournament",
            f"Football at the {year} Summer Olympics – Women's tournament",
        ]
        titles: List[str] = []
        seen: Set[str] = set()
        for seed in seeds:
            try:
                html = self.client.get_html(seed)
            except Exception:
                continue
            if seed not in seen:
                seen.add(seed)
                titles.append(seed)
            soup = BeautifulSoup(html, "lxml")
            for a in soup.select("div.mw-parser-output a[href^='/wiki/']"):
                title = unquote(a["href"].split("/wiki/", 1)[-1].replace("_", " "))
                if f"Football at the {year} Summer Olympics" not in title:
                    continue
                # stay inside this edition's football subgraph
                if any(
                    k in title
                    for k in (
                        "Group",
                        "Knockout",
                        "Final",
                        "final",
                        "squad",
                        "Squad",
                        "tournament",
                        "Tournament",
                        "match",
                        "Match",
                    )
                ) or title.startswith(f"Football at the {year} Summer Olympics"):
                    if title not in seen and not title.startswith(("Template:", "Talk:", "Special:")):
                        seen.add(title)
                        titles.append(title)
        return titles

    def parse_footballboxes(self, soup: BeautifulSoup, games_id: str, sport_id: int, source_url: str) -> int:
        added = 0
        for box in soup.select("div.footballbox"):
            text = _clean(" ".join(box.stripped_strings))
            # Typical: "26 August 1960 21:00 Bulgaria 3–0 Turkey ..."
            score_m = split_score_line(text)
            if not score_m:
                # try structured children
                home_el = box.select_one(".fhome, .home")
                away_el = box.select_one(".faway, .away")
                score_el = box.select_one(".fscore, .score")
                date_el = box.select_one(".fdate, .date")
                if not (home_el and away_el and score_el):
                    continue
                home = _clean(home_el.get_text(" ", strip=True))
                away = _clean(away_el.get_text(" ", strip=True))
                sc = _clean(score_el.get_text(" ", strip=True))
                sm = SCORE_CELL.match(sc)
                if not sm:
                    continue
                hg, ag = sm.group(1), sm.group(2)
                match_date = _parse_date(date_el.get_text(" ", strip=True) if date_el else "")
            else:
                # Ambiguous left side includes date + home
                left = _clean(score_m[0])
                hg, ag = score_m[1], score_m[2]
                away = _clean(score_m[3])
                # Split date from home team: last token(s) after time or year
                dm = re.match(
                    r"^(\d{1,2}\s+\w+\s+\d{4}(?:\s+\d{1,2}:\d{2})?)\s+(.+)$",
                    left,
                )
                if dm:
                    match_date = _parse_date(dm.group(1))
                    home = _clean(dm.group(2))
                else:
                    match_date = None
                    home = left

            home_team = self._ensure_team(games_id, sport_id, home)
            away_team = self._ensure_team(games_id, sport_id, away)

            # de-dupe rough
            exists = self.session.scalar(
                select(Match).where(
                    Match.games_id == games_id,
                    Match.home_team_id == home_team.team_id,
                    Match.away_team_id == away_team.team_id,
                    Match.home_score == hg,
                    Match.away_score == ag,
                    Match.source_url == source_url,
                )
            )
            if exists:
                continue

            stage = None
            if "final" in source_url.lower():
                stage = "final"
            elif "knockout" in source_url.lower():
                stage = "knockout"
            elif "group" in source_url.lower():
                stage = "group"

            match = Match(
                games_id=games_id,
                sport_id=sport_id,
                tournament_name="Olympic Football",
                match_date=match_date,
                match_stage=stage,
                group_name=None,
                home_team_id=home_team.team_id,
                away_team_id=away_team.team_id,
                home_score=hg,
                away_score=ag,
                match_status="played",
                source_url=source_url,
                verification_status="collected",
            )
            self.session.add(match)
            self.session.flush()
            # winner
            try:
                winner = home_team.team_id if int(hg) > int(ag) else (
                    away_team.team_id if int(ag) > int(hg) else None
                )
            except ValueError:
                winner = None
            self.session.add(
                MatchResult(
                    match_id=match.match_id,
                    winner_team_id=winner,
                    verification_status="collected",
                )
            )
            added += 1
        return added

    def parse_squads(self, soup: BeautifulSoup, games_id: str, sport_id: int, source_url: str) -> int:
        """Parse squad sections: heading = country, then player lists/tables."""
        added = 0
        # Common pattern: h3/h2 country name then ul/ol or wikitable
        headings = soup.select("h2, h3, h4")
        for heading in headings:
            country = _clean(heading.get_text(" ", strip=True))
            if not country or country.lower() in {
                "references", "see also", "external links", "notes", "contents", "squads"
            }:
                continue
            # skip non-country-ish short noise
            if len(country) < 3 or len(country) > 60:
                continue
            team = self._ensure_team(games_id, sport_id, country)
            # collect following lists until next heading
            players: List[str] = []
            for sib in heading.find_all_next(["ul", "ol", "table", "h2", "h3", "h4"], limit=12):
                if sib.name in {"h2", "h3", "h4"}:
                    break
                if sib.name in {"ul", "ol"}:
                    for li in sib.select(":scope > li"):
                        name = _clean(li.get_text(" ", strip=True))
                        # strip numbers / positions prefixes
                        name = re.sub(r"^\d+\s*[.\-]?\s*", "", name)
                        name = re.split(r"\(|–|—", name)[0].strip()
                        if name and 2 < len(name) < 80:
                            players.append(name)
                if sib.name == "table" and "wikitable" in (sib.get("class") or []):
                    # player name often in a column
                    headers = [th.get_text(" ", strip=True).lower() for th in sib.select("tr th")]
                    name_i = next((i for i, h in enumerate(headers) if "player" in h or "name" in h), 1 if headers else 0)
                    for tr in sib.select("tr")[1:]:
                        cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
                        if not cells:
                            continue
                        idx = name_i if name_i < len(cells) else 0
                        name = _clean(cells[idx])
                        name = re.split(r"\(|–|—", name)[0].strip()
                        if name and 2 < len(name) < 80:
                            players.append(name)
                if players and sib.name in {"h2", "h3", "h4"}:
                    break
            for pname in players:
                # link athlete if exists by name (best-effort)
                identity = f"football_squad:{games_id}:{team.team_id}:{pname.lower()}"
                athlete = self.session.scalar(
                    select(Athlete).where(Athlete.identity_key == identity)
                )
                if not athlete:
                    athlete = self.session.scalar(
                        select(Athlete).where(Athlete.full_name == pname).limit(1)
                    )
                if not athlete:
                    athlete = Athlete(
                        full_name=pname,
                        identity_key=identity,
                        source_url=source_url,
                        verification_status="collected",
                    )
                    self.session.add(athlete)
                    self.session.flush()
                exists = self.session.scalar(
                    select(TeamMember).where(
                        TeamMember.team_id == team.team_id,
                        TeamMember.athlete_id == athlete.athlete_id,
                    )
                )
                if exists:
                    continue
                self.session.add(
                    TeamMember(
                        team_id=team.team_id,
                        athlete_id=athlete.athlete_id,
                        role="player",
                        verification_status="collected",
                    )
                )
                added += 1
        self.session.commit()
        return added

    def scrape_edition(self, edition: OlympicEdition) -> Dict[str, Any]:
        if edition.season != "summer":
            return {"games_id": edition.games_id, "skipped": "winter_no_football"}
        sport = self._ensure_sport()
        titles = self.discover_football_links(edition)
        out_dir = self.raw_root / edition.games_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pages.json").write_text(
            json.dumps(titles, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        matches_added = 0
        squads_added = 0
        pages_ok = 0
        for title in titles:
            try:
                html = self.client.get_html(title)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Football page miss %s: %s", title, exc)
                continue
            safe = re.sub(r"[^\w\-]+", "_", title)[:140]
            (out_dir / f"{safe}.html").write_text(html, encoding="utf-8")
            soup = BeautifulSoup(html, "lxml")
            url = title_to_url(title)
            m = self.parse_footballboxes(soup, edition.games_id, sport.sport_id, url)
            matches_added += m
            if "squad" in title.lower():
                squads_added += self.parse_squads(soup, edition.games_id, sport.sport_id, url)
            pages_ok += 1
            self.session.commit()

        result = {
            "games_id": edition.games_id,
            "pages": len(titles),
            "pages_ok": pages_ok,
            "matches_added": matches_added,
            "squad_members_added": squads_added,
        }
        (out_dir / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def scrape_all_summer(self) -> dict:
        results = []
        for edition in SUMMER_EDITIONS:
            logger.info("Football scrape %s", edition.games_id)
            try:
                results.append({"ok": True, **self.scrape_edition(edition)})
            except Exception as exc:  # noqa: BLE001
                logger.exception(edition.games_id)
                self.session.rollback()
                results.append({"ok": False, "games_id": edition.games_id, "error": str(exc)})
        summary = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "editions_ok": sum(1 for r in results if r.get("ok")),
            "matches_total": sum(r.get("matches_added", 0) for r in results if r.get("ok")),
            "squad_members_total": sum(r.get("squad_members_added", 0) for r in results if r.get("ok")),
            "results": results,
            "already_had": {
                "football_athlete_participations": "yes (from athlete_events CSV)",
                "matches_before": "0",
                "squads_before": "0",
            },
        }
        Path("reports/scraping/football_wikipedia.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
        return summary
