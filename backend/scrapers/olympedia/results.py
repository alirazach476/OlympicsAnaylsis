"""Scrape Olympedia edition results + nested match fixtures.

Index: https://www.olympedia.org/editions/results
Edition: /editions/{id}/result
Event:   /results/{id}
Match:   nested /results/{id} linked as "Match #N"
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.core import Event, Match, MatchResult, Sport, Team
from backend.scrapers.olympedia.editions import (
    OLYMPEDIA_EDITION_IDS,
    edition_result_url,
)

logger = logging.getLogger(__name__)
BASE = "https://www.olympedia.org"


# Labels that are match-like pages (the old pattern missed Play-Off / Barrage / Final / Bout 1/2 style links)
MATCH_LABEL_RE = re.compile(r"(?i)\b(match|bout|game|play-?off|barrage|tie-?break|replay|duel|final)\b")
# references to earlier Games / athletes' history on a results page - never part of this edition
HISTORICAL_LABEL_RE = re.compile(r"\b(18|19|20)\d\d\b|olympics|this (event|class)|medalist|champion", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _parse_date(text: str) -> Optional[date]:
    text = re.sub(r"\s*[—–-]\s*\d{1,2}:\d{2}.*$", "", _clean(text))
    if not text:
        return None
    try:
        return dateparser.parse(text, fuzzy=True).date()
    except Exception:
        return None


def _int_or_none(text: str) -> Optional[int]:
    m = re.match(r"^(\d+)", _clean(text) or "")
    return int(m.group(1)) if m else None


@dataclass
class EventRef:
    games_id: str
    olympedia_edition_id: int
    sport_name: str
    event_name: str
    result_id: str
    url: str


@dataclass
class StandingRow:
    position: Optional[int]
    competitor: str
    noc: Optional[str]
    result_value: Optional[str]
    medal: Optional[str]
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class MatchFixture:
    games_id: str
    sport_name: str
    event_name: str
    match_label: str
    result_id: str
    url: str
    match_date: Optional[str] = None
    location: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_noc: Optional[str] = None
    away_noc: Optional[str] = None
    home_score: Optional[str] = None
    away_score: Optional[str] = None
    period_scores: Optional[str] = None
    stage: Optional[str] = None
    participants: Optional[List[Dict[str, Any]]] = None  # bouts/games: rows of competitor/noc/result/medal


class OlympediaResultsScraper:
    def __init__(
        self,
        session: Optional[Session] = None,
        *,
        delay: Optional[float] = None,
        force_refresh: bool = False,
    ) -> None:
        self.db = session
        self.settings = get_settings()
        self.delay = (
            delay
            if delay is not None
            else min(0.35, float(self.settings.wiki_request_delay_seconds or 0.35))
        )
        self.force_refresh = force_refresh
        self.raw_dir = self.settings.project_root / "data" / "raw" / "olympedia"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": self.settings.wiki_user_agent})
        self._last_fetch = 0.0

    def _sleep(self) -> None:
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def fetch_html(self, url: str, cache_name: str) -> Optional[str]:
        path = self.raw_dir / cache_name
        if path.exists() and not self.force_refresh and path.stat().st_size > 200:
            return path.read_text(encoding="utf-8", errors="replace")
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(8):
            self._sleep()
            try:
                resp = self.http.get(url, timeout=90)
                self._last_fetch = time.monotonic()
            except requests.RequestException as exc:
                logger.warning("fetch failed %s: %s", url, exc)
                time.sleep(min(30, 2 ** attempt))
                continue
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and str(retry_after).isdigit()
                    else min(60.0, 3.0 * (2 ** attempt))
                )
                logger.warning(
                    "HTTP 429 for %s — backing off %.1fs (attempt %s)",
                    url,
                    wait,
                    attempt + 1,
                )
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                logger.warning("HTTP %s for %s", resp.status_code, url)
                return None
            # Olympedia serves UTF-8 without a charset header; requests would
            # otherwise guess ISO-8859-1 and garble names (MÃ¼ller).
            text = resp.content.decode("utf-8", errors="replace")
            path.write_text(text, encoding="utf-8")
            return text
        logger.warning("gave up fetching %s after retries", url)
        return None

    def parse_edition_index(self, games_id: str, html: str, edition_id: int) -> List[EventRef]:
        soup = BeautifulSoup(html, "lxml")
        events: List[EventRef] = []
        current_sport = "Unknown"
        table = soup.select_one("table")
        if not table:
            return events
        for tr in table.select("tr"):
            links = tr.select("a[href]")
            if not links:
                continue
            href = links[0].get("href") or ""
            label = _clean(links[0].get_text(" ", strip=True))
            if "/sports/" in href:
                current_sport = label
                continue
            m = re.search(r"/results/(\d+)", href)
            if not m:
                continue
            rid = m.group(1)
            events.append(
                EventRef(
                    games_id=games_id,
                    olympedia_edition_id=edition_id,
                    sport_name=current_sport,
                    event_name=label,
                    result_id=rid,
                    url=urljoin(BASE, href),
                )
            )
        return events

    def _header_map(self, table: Tag) -> Dict[str, int]:
        header_row = table.select_one("tr")
        if not header_row:
            return {}
        headers = [_clean(th.get_text(" ", strip=True)).lower() for th in header_row.select("th,td")]
        out: Dict[str, int] = {}
        for i, h in enumerate(headers):
            out[h] = i
        return out

    def _pick(self, cells: List[str], headers: Dict[str, int], *names: str) -> Optional[str]:
        for name in names:
            idx = headers.get(name.lower())
            if idx is not None and idx < len(cells):
                val = _clean(cells[idx])
                if val:
                    return val
        return None

    def parse_sub_selects(self, html: str) -> List[Dict[str, str]]:
        """Extract phase dropdowns: Run #N, Standings after Run #N, heats, etc.

        Ignores navigation dropdowns (same_games_select / other_games_select).
        """
        soup = BeautifulSoup(html, "lxml")
        out: List[Dict[str, str]] = []
        seen: Set[str] = set()
        for sel in soup.select("select[id]"):
            sid = sel.get("id") or ""
            if sid in {"same_games_select", "other_games_select"}:
                continue
            if not (
                sid.startswith("sub_select_for_")
                or re.search(r"(?i)run|stand|heat|round|phase|part|qual|final", sid)
            ):
                # still allow unknown sub dropdowns that clearly point at /results/ids
                if not sid.startswith("sub_select"):
                    continue
            group = "runs" if "run" in sid.lower() else "standings" if "stand" in sid.lower() else sid
            for opt in sel.select("option"):
                val = (opt.get("value") or "").strip()
                label = _clean(opt.get_text(" ", strip=True))
                if not val or not val.isdigit():
                    continue
                if val in seen:
                    continue
                seen.add(val)
                out.append(
                    {
                        "group": group,
                        "select_id": sid,
                        "label": label,
                        "result_id": val,
                        "url": f"{BASE}/results/{val}",
                    }
                )
        return out

    def parse_event_page(self, html: str) -> Tuple[List[StandingRow], List[Tuple[str, str]], Dict[str, str]]:
        """Return standings, nested (label, /results/id) links, meta."""
        soup = BeautifulSoup(html, "lxml")
        title = _clean(soup.select_one("h1").get_text(" ", strip=True)) if soup.select_one("h1") else ""
        meta: Dict[str, str] = {"title": title}
        biodata = soup.select_one("table.biodata")
        if biodata:
            rows = biodata.select("tr")
            for tr in rows:
                cells = [_clean(c.get_text(" ", strip=True)) for c in tr.select("th,td")]
                if len(cells) >= 2:
                    meta[cells[0].lower()] = cells[1]

        nested: List[Tuple[str, str]] = []
        seen: Set[str] = set()
        for a in soup.select("a[href*='/results/']"):
            href = a.get("href") or ""
            m = re.search(r"/results/(\d+)", href)
            if not m:
                continue
            label = _clean(a.get_text(" ", strip=True))
            rid = m.group(1)
            key = f"{rid}:{label}"
            if key in seen:
                continue
            seen.add(key)
            # keep match-like and phase links
            if re.search(r"(?i)\bmatch\b|#\d+|final|semi|quarter|group|round", label) or label.startswith("Match"):
                nested.append((label, href if href.startswith("http") else urljoin(BASE, href)))

        standings: List[StandingRow] = []
        for table in soup.select("table"):
            headers = self._header_map(table)
            if not headers:
                continue
            keys = set(headers)
            if not ({"pos", "position"} & keys) and not ({"competitor", "competitors", "team"} & keys):
                continue
            # skip tiny biodata-like
            if "date" in keys and "location" in keys and not ({"competitor", "competitors"} & keys):
                continue
            cur_team = None
            cur_noc = None
            for tr in table.select("tr")[1:]:
                tds = tr.select("td")
                cells = [_clean(td.get_text(" ", strip=True)) for td in tds]
                if len(cells) < 2:
                    continue
                competitor = self._pick(
                    cells, headers, "competitor", "competitors", "team", "athlete", "athletes",
                    "name", "pair", "crew", "skater", "skaters", "driver", "player", "players",
                )
                if not competitor:
                    # fallback: first non-structural column after Pos
                    skip = {"pos", "position", "number", "bib", "noc", "country", ""}
                    for h, idx in sorted(headers.items(), key=lambda kv: kv[1]):
                        if h not in skip and idx < len(cells) and cells[idx]:
                            competitor = cells[idx]
                            break
                if not competitor or competitor.lower() in {"competitor", "team"}:
                    continue
                pos_raw = self._pick(cells, headers, "pos", "position") or ""
                medal = self._pick(cells, headers, "medal", "")
                # medal often last empty-header cell with Gold/Silver/Bronze
                if not medal:
                    for c in cells:
                        if c in {"Gold", "Silver", "Bronze"}:
                            medal = c
                            break
                result_value = self._pick(
                    cells,
                    headers,
                    "result",
                    "time",
                    "points",
                    "score",
                    "goals",
                    "distance",
                    "mark",
                    "total points",
                    "wins",
                )
                noc = self._pick(cells, headers, "noc", "country")
                extra: Dict[str, str] = {}
                for td in tds:
                    a = td.select_one("a[href*='/athletes/']")
                    if a:
                        m = re.search(r"/athletes/(\d+)", a.get("href") or "")
                        if m:
                            extra["athlete_id"] = m.group(1)
                        break
                bib = self._pick(cells, headers, "number", "bib")
                if bib:
                    extra["bib"] = bib
                m_pos = re.fullmatch(r"=?T?(\d+)", pos_raw)
                pos_int = int(m_pos.group(1)) if m_pos else None
                # keep every other column (run times, ordinals, wins/losses...) so nothing on the page is lost
                used = {"pos", "position", "number", "bib", "noc", "country", "medal", ""}
                for h, idx in headers.items():
                    if h not in used and idx < len(cells) and cells[idx] and cells[idx] != competitor and cells[idx] != result_value:
                        extra[h] = cells[idx]
                if pos_raw and pos_int is None and not re.fullmatch(r"(?i)(dnf|dns|dsq|disq\w*|ac|nm|—|-|dq|ret)", pos_raw):
                    # team-event member row (Lead-Off, 2nd Leg, Anchor, Driver ...)
                    extra["role"] = pos_raw
                    if cur_team:
                        extra["team"] = cur_team
                    noc = noc or cur_noc
                    medal = None
                else:
                    cur_team, cur_noc = competitor, noc
                standings.append(
                    StandingRow(
                        position=pos_int,
                        competitor=competitor,
                        noc=noc,
                        result_value=result_value,
                        medal=medal,
                        extra=extra,
                    )
                )
            if standings:
                break
        return standings, nested, meta

    def parse_match_page(
        self,
        games_id: str,
        sport_name: str,
        event_name: str,
        match_label: str,
        result_id: str,
        url: str,
        html: str,
    ) -> MatchFixture:
        soup = BeautifulSoup(html, "lxml")
        title = _clean(soup.select_one("h1").get_text(" ", strip=True)) if soup.select_one("h1") else match_label
        fx = MatchFixture(
            games_id=games_id,
            sport_name=sport_name,
            event_name=event_name,
            match_label=title or match_label,
            result_id=result_id,
            url=url,
            stage=match_label,
        )
        biodata = soup.select_one("table.biodata")
        if biodata:
            for tr in biodata.select("tr"):
                cells = [_clean(c.get_text(" ", strip=True)) for c in tr.select("th,td")]
                if len(cells) >= 2:
                    key = cells[0].lower()
                    if key == "date":
                        fx.match_date = cells[1]
                    elif key == "location":
                        fx.location = cells[1]

        # Prefer compact team scoreboards (2 rows + NOC) over player roster tables.
        candidates = []
        for table in soup.select("table"):
            headers = self._header_map(table)
            if not headers:
                continue
            if "competitor" not in headers and "team" not in headers:
                continue
            score_keys = ("sets won", "goals", "result", "score", "points", "runs")
            if not any(k in headers for k in score_keys):
                continue
            rows = []
            for tr in table.select("tr")[1:]:
                cells = [_clean(td.get_text(" ", strip=True)) for td in tr.select("td")]
                if len(cells) < 2:
                    continue
                name = self._pick(cells, headers, "competitor", "team")
                noc = self._pick(cells, headers, "noc")
                score = self._pick(cells, headers, "sets won", "goals", "result", "score", "points", "runs")
                half1 = self._pick(cells, headers, "half #1", "1st", "period 1", "set #1")
                half2 = self._pick(cells, headers, "half #2", "2nd", "period 2", "set #2")
                if name:
                    rows.append((name, noc, score, half1, half2))
            if len(rows) < 2:
                continue
            with_noc = sum(1 for r in rows if r[1])
            # team boards usually have NOC on both sides and few rows
            score_priority = 0
            for k in ("sets won", "goals", "result", "score", "runs"):
                if k in headers:
                    score_priority = 2
                    break
            if "points" in headers and score_priority == 0:
                score_priority = 1
            rank = (with_noc >= 2, score_priority, -abs(len(rows) - 2), -len(rows))
            candidates.append((rank, rows))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            rows = candidates[0][1][:2]
            # reject player-roster false positives: no NOCs and dash-only scores
            if rows[0][1] or rows[1][1] or (
                rows[0][2] and rows[0][2] not in {"–", "-", "—", ""}
            ):
                fx.home_team, fx.home_noc, fx.home_score = rows[0][0], rows[0][1], rows[0][2]
                fx.away_team, fx.away_noc, fx.away_score = rows[1][0], rows[1][1], rows[1][2]
                periods = []
                if rows[0][3] is not None or rows[1][3] is not None:
                    periods.append(f"P1 {rows[0][3] or '-'}-{rows[1][3] or '-'}")
                if rows[0][4] is not None or rows[1][4] is not None:
                    periods.append(f"P2 {rows[0][4] or '-'}-{rows[1][4] or '-'}")
                if periods:
                    fx.period_scores = "; ".join(periods)
        return fx

    def _edition_dir(self, games_id: str) -> Path:
        d = self.raw_dir / "editions" / games_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def scrape_edition_catalog(self, games_id: str) -> List[EventRef]:
        edition_id = OLYMPEDIA_EDITION_IDS[games_id]
        url = edition_result_url(edition_id)
        html = self.fetch_html(url, f"editions/{games_id}/index_result.html")
        if not html:
            return []
        events = self.parse_edition_index(games_id, html, edition_id)
        out = self._edition_dir(games_id) / "events_catalog.json"
        out.write_text(
            json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("%s catalog events=%s", games_id, len(events))
        return events

    def scrape_event(
        self,
        ref: EventRef,
        *,
        follow_matches: bool = True,
        max_matches: Optional[int] = None,
    ) -> Dict[str, Any]:
        cache = f"editions/{ref.games_id}/events/{ref.result_id}.html"
        html = self.fetch_html(ref.url, cache)
        if not html:
            return {"ok": False, "result_id": ref.result_id}
        standings, nested, meta = self.parse_event_page(html)
        sub_links = self.parse_sub_selects(html)
        payload = {
            "games_id": ref.games_id,
            "sport_name": ref.sport_name,
            "event_name": ref.event_name,
            "result_id": ref.result_id,
            "url": ref.url,
            "meta": meta,
            "standings": [asdict(s) for s in standings],
            "nested_links": [{"label": a, "url": b} for a, b in nested],
            "sub_select_links": sub_links,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        json_path = self._edition_dir(ref.games_id) / "events" / f"{ref.result_id}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        self._phase_nested, self._phase_seen = [], set()
        phases_fetched = self.scrape_sub_phases(ref, sub_links)
        # links on the event page AND on every dropdown page (Bout 1/2, Play-Off, Barrage, Final ...)
        seen_links, all_nested = set(), []
        for lab, u in list(nested) + list(self._phase_nested):
            if u not in seen_links and not HISTORICAL_LABEL_RE.search(lab or ""):
                seen_links.add(u)
                all_nested.append((lab, u))
        nested = all_nested

        fixtures: List[MatchFixture] = []
        if follow_matches and nested:
            match_links = [(lab, u) for lab, u in nested if MATCH_LABEL_RE.search(lab or "")]
            if max_matches is not None:
                match_links = match_links[:max_matches]
            for lab, u in match_links:
                m = re.search(r"/results/(\d+)", u)
                if not m:
                    continue
                rid = m.group(1)
                fpath = self._edition_dir(ref.games_id) / "matches" / f"{rid}.json"
                if fpath.exists() and not self.force_refresh:
                    try:
                        data = json.loads(fpath.read_text(encoding="utf-8"))
                        # Require NOCs (team board) — skip cache if player-roster misparse
                        if data.get("participants") or (
                            data.get("home_team")
                            and data.get("away_team")
                            and (data.get("home_noc") or data.get("away_noc"))
                        ):
                            fixtures.append(
                                MatchFixture(**{k: data.get(k) for k in MatchFixture.__dataclass_fields__})
                            )
                            continue
                    except Exception:
                        pass
                mhtml = self.fetch_html(u, f"editions/{ref.games_id}/matches/{rid}.html")
                if not mhtml:
                    continue
                fx = self.parse_match_page(
                    ref.games_id, ref.sport_name, ref.event_name, lab, rid, u, mhtml
                )
                try:
                    fx.participants = [asdict(r) for r in self.parse_event_page(mhtml)[0]]
                except Exception:
                    fx.participants = None
                fixtures.append(fx)
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(json.dumps(asdict(fx), ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "ok": True,
            "result_id": ref.result_id,
            "standings": len(standings),
            "fixtures": fixtures,
            "nested": len(nested),
            "sub_phases": phases_fetched,
        }

    def scrape_sub_phases(self, ref: EventRef, sub_links: List[Dict[str, str]]) -> int:
        """Fetch Run/Standings/heat dropdown pages for one parent event."""
        fetched = 0
        self._phase_nested = getattr(self, "_phase_nested", [])
        seen = getattr(self, "_phase_seen", set())
        self._phase_seen = seen
        queue = list(sub_links)
        while queue:
            link = queue.pop(0)
            rid = link["result_id"]
            # never re-fetch the parent event as a "phase" (nor a page already visited: dropdowns link to each other)
            if rid == ref.result_id or rid in seen:
                continue
            seen.add(rid)
            cache = f"editions/{ref.games_id}/phases/{rid}.html"
            html = self.fetch_html(link["url"], cache)
            if not html:
                continue
            standings, nested, meta = self.parse_event_page(html)
            child_subs = self.parse_sub_selects(html)
            queue.extend(c for c in child_subs if c["result_id"] not in seen)  # dropdowns inside dropdown pages
            self._phase_nested.extend(nested)  # match / bout links found on phase pages
            out = {
                "games_id": ref.games_id,
                "parent_result_id": ref.result_id,
                "parent_event_name": ref.event_name,
                "sport_name": ref.sport_name,
                "phase_label": link.get("label"),
                "phase_group": link.get("group"),
                "select_id": link.get("select_id"),
                "result_id": rid,
                "url": link["url"],
                "meta": meta,
                "standings": [asdict(s) for s in standings],
                "nested_links": [{"label": a, "url": b} for a, b in nested],
                "sub_select_links": child_subs,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            jpath = self._edition_dir(ref.games_id) / "phases" / f"{rid}.json"
            jpath.parent.mkdir(parents=True, exist_ok=True)
            jpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            fetched += 1
        return fetched

    def _ensure_sport(self, name: str, season: Optional[str] = None) -> Sport:
        assert self.db is not None
        sport = self.db.scalar(select(Sport).where(Sport.sport_name == name))
        if sport:
            return sport
        sport = Sport(
            sport_name=name,
            season=season,
            source_url=BASE,
            verification_status="collected",
        )
        self.db.add(sport)
        self.db.flush()
        return sport

    def _ensure_team(self, games_id: str, sport_id: int, name: str, noc: Optional[str]) -> Team:
        assert self.db is not None
        name = _clean(name)
        existing = self.db.scalar(
            select(Team).where(
                Team.games_id == games_id,
                Team.sport_id == sport_id,
                Team.team_name == name,
            )
        )
        if existing:
            if noc and not existing.noc_code:
                existing.noc_code = noc
            return existing
        team = Team(
            games_id=games_id,
            sport_id=sport_id,
            noc_code=noc,
            team_name=name,
            source_url=BASE,
            verification_status="collected",
        )
        self.db.add(team)
        self.db.flush()
        return team

    def _commit_retry(self) -> None:
        assert self.db is not None
        for attempt in range(8):
            try:
                self.db.commit()
                return
            except OperationalError as exc:
                self.db.rollback()
                logger.warning("DB lock retry %s: %s", attempt + 1, exc)
                time.sleep(0.5 * (attempt + 1))
        self.db.commit()

    def load_fixture(self, fx: MatchFixture) -> bool:
        """Upsert a match by source_url. Returns True if inserted/updated."""
        if self.db is None:
            return False
        if not fx.home_team or not fx.away_team:
            # still store skeleton if URL known
            if not fx.url:
                return False

        existing = self.db.scalar(select(Match).where(Match.source_url == fx.url))
        season = "winter" if "winter" in fx.games_id else "summer"
        sport = self._ensure_sport(fx.sport_name, season)
        home = (
            self._ensure_team(fx.games_id, sport.sport_id, fx.home_team, fx.home_noc)
            if fx.home_team
            else None
        )
        away = (
            self._ensure_team(fx.games_id, sport.sport_id, fx.away_team, fx.away_noc)
            if fx.away_team
            else None
        )
        mdate = _parse_date(fx.match_date or "")
        if existing:
            existing.home_team_id = home.team_id if home else existing.home_team_id
            existing.away_team_id = away.team_id if away else existing.away_team_id
            existing.home_score = fx.home_score or existing.home_score
            existing.away_score = fx.away_score or existing.away_score
            existing.period_scores = fx.period_scores or existing.period_scores
            existing.match_date = mdate or existing.match_date
            existing.match_stage = fx.stage or existing.match_stage
            existing.tournament_name = fx.event_name or existing.tournament_name
            existing.match_status = "completed" if fx.home_score is not None else existing.match_status
            existing.verification_status = "collected"
            match = existing
        else:
            match = Match(
                games_id=fx.games_id,
                sport_id=sport.sport_id,
                tournament_name=fx.event_name,
                match_date=mdate,
                match_stage=fx.stage or fx.match_label,
                home_team_id=home.team_id if home else None,
                away_team_id=away.team_id if away else None,
                home_score=fx.home_score,
                away_score=fx.away_score,
                period_scores=fx.period_scores,
                match_status="completed" if fx.home_score is not None else "collected",
                source_url=fx.url,
                verification_status="collected",
            )
            self.db.add(match)
            self.db.flush()

        # simple match_result row if scores present
        if fx.home_score is not None and fx.away_score is not None:
            mr = self.db.scalar(select(MatchResult).where(MatchResult.match_id == match.match_id))
            winner = None
            try:
                hs = float(re.sub(r"[^\d.]", "", fx.home_score) or "nan")
                as_ = float(re.sub(r"[^\d.]", "", fx.away_score) or "nan")
                if hs > as_ and home:
                    winner = home.team_id
                elif as_ > hs and away:
                    winner = away.team_id
            except ValueError:
                winner = None
            if mr:
                mr.winner_team_id = winner
                mr.notes = fx.location
            else:
                self.db.add(
                    MatchResult(
                        match_id=match.match_id,
                        winner_team_id=winner,
                        notes=fx.location,
                        verification_status="collected",
                    )
                )
        return True

    def ensure_event_row(self, ref: EventRef) -> None:
        if self.db is None:
            return
        season = "winter" if "winter" in ref.games_id else "summer"
        sport = self._ensure_sport(ref.sport_name, season)
        gender = None
        low = ref.event_name.lower()
        if low.endswith(", men") or ", men" in low:
            gender = "Men"
        elif low.endswith(", women") or ", women" in low:
            gender = "Women"
        elif "mixed" in low:
            gender = "Mixed"
        existing = self.db.scalar(
            select(Event).where(
                Event.games_id == ref.games_id,
                Event.event_name == ref.event_name,
                Event.sport_id == sport.sport_id,
            )
        )
        if existing:
            if not existing.source_url:
                existing.source_url = ref.url
            return
        # discipline_id optional; unique constraint needs discipline_id — may be NULL multiple times on sqlite
        self.db.add(
            Event(
                games_id=ref.games_id,
                sport_id=sport.sport_id,
                discipline_id=None,
                event_name=ref.event_name,
                event_gender=gender,
                source_url=ref.url,
                verification_status="collected",
            )
        )

    def _event_json_path(self, games_id: str, result_id: str) -> Path:
        return self._edition_dir(games_id) / "events" / f"{result_id}.json"

    def is_event_done(self, games_id: str, result_id: str) -> bool:
        """True if event JSON checkpoint exists (safe to skip on resume)."""
        path = self._event_json_path(games_id, result_id)
        return path.exists() and path.stat().st_size > 80

    def write_checkpoint(self, payload: Dict[str, Any]) -> None:
        path = self.raw_dir / "checkpoint.json"
        payload = {
            **payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass  # another parallel scraper window is writing it

    def scrape_edition(
        self,
        games_id: str,
        *,
        follow_matches: bool = True,
        max_events: Optional[int] = None,
        sports: Optional[Iterable[str]] = None,
        load_db: bool = True,
        fixtures_only_deep: bool = False,
        skip_done: bool = True,
    ) -> Dict[str, Any]:
        if games_id not in OLYMPEDIA_EDITION_IDS:
            raise KeyError(f"No Olympedia edition mapped for {games_id}")
        events = self.scrape_edition_catalog(games_id)
        sport_filter = {s.lower() for s in sports} if sports else None
        if sport_filter:
            events = [e for e in events if e.sport_name.lower() in sport_filter]
        if max_events is not None:
            events = events[:max_events]

        fixtures_loaded = 0
        events_ok = 0
        events_skipped = 0
        standings_rows = 0
        all_fixtures: List[MatchFixture] = []

        for i, ref in enumerate(events, 1):
            if skip_done and not self.force_refresh and self.is_event_done(ref.games_id, ref.result_id):
                events_skipped += 1
                events_ok += 1
                self.write_checkpoint(
                    {
                        "games_id": games_id,
                        "event_index": i,
                        "event_total": len(events),
                        "result_id": ref.result_id,
                        "sport_name": ref.sport_name,
                        "event_name": ref.event_name,
                        "status": "skipped_cached",
                        "events_ok": events_ok,
                        "events_skipped": events_skipped,
                    }
                )
                if i % 50 == 0:
                    logger.info(
                        "%s skip-cached %s/%s (skipped=%s)",
                        games_id,
                        i,
                        len(events),
                        events_skipped,
                    )
                continue

            result = self.scrape_event(
                ref,
                follow_matches=follow_matches,
                max_matches=None,
            )
            if not result.get("ok"):
                self.write_checkpoint(
                    {
                        "games_id": games_id,
                        "event_index": i,
                        "event_total": len(events),
                        "result_id": ref.result_id,
                        "status": "fetch_failed",
                    }
                )
                continue
            events_ok += 1
            standings_rows += int(result.get("standings") or 0)
            fixtures: List[MatchFixture] = result.get("fixtures") or []
            all_fixtures.extend(fixtures)
            if load_db and self.db is not None:
                try:
                    self.ensure_event_row(ref)
                    for fx in fixtures:
                        if self.load_fixture(fx):
                            fixtures_loaded += 1
                    if i % 10 == 0:
                        self._commit_retry()
                except Exception:
                    logger.exception("DB load failed for %s", ref.result_id)
                    if self.db:
                        self.db.rollback()
            self.write_checkpoint(
                {
                    "games_id": games_id,
                    "event_index": i,
                    "event_total": len(events),
                    "result_id": ref.result_id,
                    "sport_name": ref.sport_name,
                    "event_name": ref.event_name,
                    "status": "scraped",
                    "standings": result.get("standings"),
                    "fixtures": len(fixtures),
                    "events_ok": events_ok,
                    "events_skipped": events_skipped,
                }
            )
            logger.info(
                "%s event %s/%s %s/%s standings=%s fixtures=%s",
                games_id,
                i,
                len(events),
                ref.sport_name,
                ref.event_name,
                result.get("standings"),
                len(fixtures),
            )

        if load_db and self.db is not None:
            self._commit_retry()

        summary = {
            "games_id": games_id,
            "olympedia_edition_id": OLYMPEDIA_EDITION_IDS[games_id],
            "catalog_events": len(events),
            "events_scraped": events_ok,
            "events_skipped_cached": events_skipped,
            "standings_rows": standings_rows,
            "fixtures_found": len(all_fixtures),
            "fixtures_loaded": fixtures_loaded,
            "source": "olympedia",
            "index_url": edition_result_url(OLYMPEDIA_EDITION_IDS[games_id]),
        }
        (self._edition_dir(games_id) / "scrape_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        self.write_checkpoint(
            {
                "games_id": games_id,
                "status": "edition_done",
                **summary,
            }
        )
        return summary
