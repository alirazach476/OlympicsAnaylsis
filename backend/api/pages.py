"""Endpoints for the redesigned pages: saved Olympedia pages exactly as they appear (every table), bouts / duels of individual sports, a global search, and a country at one Games.
Everything is read from the warehouse (olympedia_pages, olympedia_page_tables, olympedia_country_page_tables, olympedia_matches ...); nothing is computed from invented data."""
from __future__ import annotations

import json
import zlib
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.platform import one, page, rows

router = APIRouter()


def _loads(s):
    try:
        if isinstance(s, (bytes, memoryview)):  # slim deployment DB stores large JSON zlib-compressed
            s = zlib.decompress(bytes(s)).decode("utf-8")
        return json.loads(s) if s else None
    except Exception:  # noqa: BLE001
        return None


def _dedupe(parts):
    out = []
    for x in parts:
        if x and x not in out:
            out.append(x)
    return out


@router.get("/pages/{result_id}", tags=["pages"])
def saved_page(result_id: str):
    """One Olympedia results page as saved: title, breadcrumb, the date / location lines and every table (headers, rows, links) in page order."""
    p = one("SELECT result_id, games_id, kind, title, breadcrumb, meta_json, dropdowns_json FROM olympedia_pages WHERE result_id=:r", r=result_id)
    if not p:
        raise HTTPException(404, "page not saved")
    tables = rows("SELECT table_index, section, headers_json, rows_json, links_json FROM olympedia_page_tables WHERE result_id=:r ORDER BY table_index", r=result_id)
    return {"result_id": p["result_id"], "games_id": p["games_id"], "kind": p["kind"], "title": p["title"], "breadcrumb": " > ".join(_dedupe((p["breadcrumb"] or "").split(" > "))), "meta": _loads(p["meta_json"]) or {},
            "dropdowns": _loads(p["dropdowns_json"]) or [], "source_url": f"https://www.olympedia.org/results/{result_id}",
            "tables": [{"index": t["table_index"], "section": t["section"], "headers": _loads(t["headers_json"]), "rows": _loads(t["rows_json"]) or [], "links": _loads(t["links_json"]) or []} for t in tables]}


@router.get("/bouts", tags=["pages"])
def bouts(games_id: str, sport: str, event: Optional[str] = None, page_no: int = Query(1, alias="page"), page_size: int = Query(60, le=300)):
    """Bouts / duels / matches of individual sports (fencing, judo, wrestling, boxing ...): two competitors per page, as saved."""
    w = "WHERE games_id=:g AND sport_name=:s AND (:e IS NULL OR event_name=:e)"
    p = dict(g=games_id, s=sport, e=event)
    out = page(f"SELECT COUNT(*) FROM olympedia_matches {w}", f"SELECT result_id, event_name, label, stage, match_date, location, home_team, home_noc, home_score, away_team, away_noc, away_score, participants_json FROM olympedia_matches {w} ORDER BY event_name, match_date, result_id", page_no, page_size, **p)
    for r in out["rows"]:
        r["participants"] = _loads(r.pop("participants_json")) or []
    out["events"] = [r["event_name"] for r in rows("SELECT DISTINCT event_name FROM olympedia_matches WHERE games_id=:g AND sport_name=:s ORDER BY event_name", g=games_id, s=sport)]
    return out


@router.get("/search", tags=["search"])
def search(q: str = Query(..., min_length=2), limit: int = Query(6, le=15)):
    """Global search: editions, countries, sports and athletes (prefix / substring on the name; athletes capped to keep it fast)."""
    like, pre = f"%{q.lower()}%", f"{q.lower()}%"
    words = [w for w in q.lower().split() if w][:4]   # every word must appear in the athlete's name ("usain bolt" finds "Usain St. Leo Bolt")
    tok = {f"t{i}": f"%{w}%" for i, w in enumerate(words)}
    cond = " AND ".join(f"LOWER(a.full_name) LIKE :t{i}" for i in range(len(words))) or "1=0"
    return {
        "editions": rows("SELECT games_id, year, season, host_city, host_country FROM games WHERE LOWER(host_city) LIKE :l OR LOWER(host_country) LIKE :l OR CAST(year AS TEXT) LIKE :p ORDER BY year DESC LIMIT :n", l=like, p=pre, n=limit),
        "countries": rows("SELECT noc_code, historical_name FROM historical_nocs WHERE LOWER(historical_name) LIKE :l OR LOWER(noc_code)=:c ORDER BY historical_name LIMIT :n", l=like, c=q.lower(), n=limit),
        "sports": rows("SELECT DISTINCT sport_id, sport_name FROM sports WHERE LOWER(sport_name) LIKE :l ORDER BY sport_name LIMIT :n", l=like, n=limit),
        "athletes": rows(f"SELECT a.athlete_id, a.full_name, c.nocs, c.sports, c.medals FROM silver_athletes a LEFT JOIN gold_athlete_career c USING(athlete_id) WHERE {cond} ORDER BY COALESCE(c.medals,0) DESC LIMIT :n", n=limit, **tok),
    }


@router.get("/countries/{noc}/at/{games_id}", tags=["countries"])
def country_at_games(noc: str, games_id: str):
    """A country's results page for one Games as it appears on Olympedia (sport headings, event rows, athletes, places, medals)."""
    p = one("SELECT noc, edition_id, title, source_url FROM olympedia_country_pages WHERE noc=:n AND games_id=:g AND page_kind='country_edition'", n=noc.upper(), g=games_id)
    if not p:
        raise HTTPException(404, "country did not take part in this edition (or the page is not saved)")
    tabs = rows("SELECT table_index, section, headers_json, rows_json, links_json FROM olympedia_country_page_tables WHERE noc=:n AND games_id=:g AND page_kind='country_edition' ORDER BY table_index", n=noc.upper(), g=games_id)
    return {"noc": p["noc"], "games_id": games_id, "title": p["title"], "source_url": p["source_url"], "tables": [{"index": t["table_index"], "section": t["section"], "headers": _loads(t["headers_json"]), "rows": _loads(t["rows_json"]) or [], "links": _loads(t["links_json"]) or []} for t in tabs]}


# ---------------------------------------------------------------- broadcast graphics: match detail, record badges, event pages
import re as _re

_SCORE = _re.compile(r"^(\d+)\s*[-:]\s*(\d+)$")


def _int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:  # noqa: BLE001
        return None


_NOT_STAT = {"number", "tp", "shift #", "+/-", "pos", "competitor", "", "disqualifications"}
_STAT_PRIORITY = ["goals", "points", "assists", "shots", "shots-on-goal", "attempts", "saves", "rebounds", "steals", "blocks", "aces", "service points", "yellow cards", "red cards", "fouls committed", "penalties in minutes (pim)", "turnovers"]
_CARDS = {"yellow", "red", "yellow-red", "second yellow", "suspension", "warning", "disqualification", "2", "2.0", "5", "10"}
_SUBS = {"in", "out", "goalkeeper in", "goalkeeper out"}


def _base(name: str) -> str:
    return _re.sub(r"\s*\(.*?\)", "", name or "").strip().lower()


@router.get("/matches/{result_id}", tags=["pages"])
def match_detail(result_id: str):
    """One match for the broadcast scoreboard, read from the saved Olympedia match page: the scoreboard table (score and every period / set exactly as labelled), team statistics summed from the
    recorded player rows, goals / cards / substitutions from the event tables (the scoring side comes from matching the scorer to the line-ups), line-ups and officials. Nothing is invented:
    the match clock, shots or fouls appear only when the page records them."""
    m = one("SELECT result_id, games_id, sport_name, event_name, stage, match_date, location, home_team, home_noc, home_score, away_team, away_noc, away_score FROM olympedia_matches WHERE result_id=:r", r=result_id)
    if not m:
        raise HTTPException(404, "unknown match")
    details = {d["key"]: d["value"] for d in rows("SELECT key, value FROM olympedia_match_details WHERE result_id=:r", r=result_id)}
    tabs = rows("SELECT table_index, kind, headers_json, rows_json FROM olympedia_match_tables WHERE result_id=:r ORDER BY table_index", r=result_id)
    sb_rows, periods, score_label = [], [], None
    teams, lineups, events_tables = [], [], []
    for t in tabs:
        h, r = _loads(t["headers_json"]) or [], _loads(t["rows_json"]) or []
        if t["kind"] == "scoreboard" and r:
            i0 = h.index("NOC") + 1 if "NOC" in h else 3
            labels = [x for x in h[i0:] if x]
            score_label = labels[0] if labels else None
            for k, lab in enumerate(labels[1:], start=1):
                periods.append({"label": lab, "scores": [(_int(row[i0 + k]) if i0 + k < len(row) else None) for row in r[:2]]})
            sb_rows = r[:2]
            teams = [{"name": row[1], "noc": row[2], "score": _int(row[i0])} for row in r[:2]]
        elif t["kind"] == "players":
            lineups.append({"headers": h, "rows": r})
        elif t["kind"] == "events":
            events_tables.append(r)
    # team statistics: the page's own "Team Totals" row per team (its cells start 3 columns left of the header: Number / Competitor / blank collapse into the label)
    stats = []
    for ti, lu in enumerate(lineups[:2]):
        h = lu["headers"]
        tot = next((row for row in lu["rows"] if row and str(row[0]).strip().lower() == "team totals"), None)
        if not tot:
            continue
        for k in range(1, len(tot)):
            hi = k + 3
            if hi >= len(h):
                break
            lab = (h[hi] or "").strip()
            val = str(tot[k]).strip()
            if not lab or lab.lower() in _NOT_STAT or "line-up" in lab.lower() or val in ("", "–", "-"):
                continue
            v = _int(val)
            ent = next((x for x in stats if x["label"] == lab), None)
            if ent is None:
                ent = {"label": lab, "values": [None, None]}
                stats.append(ent)
            ent["values"][ti] = v if v is not None else val
    stats.sort(key=lambda x: (_STAT_PRIORITY.index(x["label"].lower()) if x["label"].lower() in _STAT_PRIORITY else 99, x["label"]))
    stats = [x for x in stats if x["values"][0] is not None and x["values"][1] is not None][:10]
    # players by team (name -> side) for attributing events
    side_of = {}
    for ti, lu in enumerate(lineups[:2]):
        ni = lu["headers"].index("Competitor") if "Competitor" in lu["headers"] else 2
        for row in lu["rows"]:
            if ni < len(row):
                side_of[_base(row[ni])] = "home" if ti == 0 else "away"
    total_goals = (teams[0]["score"] or 0) + (teams[1]["score"] or 0) if len(teams) == 2 and teams[0]["score"] is not None and teams[1]["score"] is not None else None
    goals, cards, subs = [], [], 0
    h = a = 0
    for er in events_tables:
        res = {str(x[3] if len(x) > 3 else "").strip().lower() for x in er}
        if res and res <= _SUBS:
            subs += len(er)
        elif res and res <= _CARDS | {""} and res != {""}:
            for x in er:
                cards.append({"time": x[0], "player": x[1], "card": (x[3] or "").lower(), "note": (x[4] if len(x) > 4 else "") or None, "side": side_of.get(_base(x[1]))})
        elif any(_SCORE.match((x[3] if len(x) > 3 else "").replace("–", "-").replace(" ", "")) for x in er):
            for x in er:
                sm = _SCORE.match((x[3] if len(x) > 3 else "").replace("–", "-").replace(" ", ""))
                side = None
                if sm:
                    nh, na = int(sm.group(1)), int(sm.group(2))
                    side = "home" if nh > h else "away" if na > a else None
                    h, a = nh, na
                goals.append({"time": x[0], "player": x[1], "score": f"{h}-{a}", "side": side or side_of.get(_base(x[1])), "note": (x[4] if len(x) > 4 else "") or None})
        elif res == {""} and total_goals is not None and len(er) == total_goals:   # a football-style goal table: no running score, but as many rows as goals
            for x in er:
                goals.append({"time": x[0], "player": x[1], "score": None, "side": side_of.get(_base(x[1])), "note": None})
    officials = {k: v for k, v in details.items() if k not in ("Date", "Location")}
    return {**m, "score_label": score_label, "teams": teams, "periods": periods, "stats": stats, "goals": goals, "cards": cards, "substitutions": subs,
            "lineups": [{"team": (teams[i]["name"] if i < len(teams) else f"Team {i + 1}"), "noc": (teams[i]["noc"] if i < len(teams) else None), "headers": lu["headers"], "rows": lu["rows"]} for i, lu in enumerate(lineups[:2])],
            "officials": officials, "source_url": f"https://www.olympedia.org/results/{result_id}",
            "notes": "Everything here is read from the saved Olympedia match page. A match clock, live status, shots or fouls are shown only when the page records them."}


@router.get("/records/for-games", tags=["records"])
def records_for_games(games_id: str):
    """Records set at one Games, so a results table can show a verified record badge: the description is '<event> | <phase> | <athlete> | <city year> | result <url>'."""
    out = []
    for r in rows("SELECT record_level, record_type, record_value, noc_code, description FROM gold_records WHERE games_id=:g", g=games_id):
        parts = [p.strip() for p in str(r["description"]).split(" | ")]
        if len(parts) >= 3:
            out.append({"level": r["record_level"], "type": r["record_type"], "value": r["record_value"], "noc": r["noc_code"], "event": parts[0], "phase": parts[1], "athlete": parts[2]})
    return out


@router.get("/event-pages", tags=["pages"])
def event_pages(games_id: str, sport: str, event: Optional[str] = None):
    """The saved Olympedia results pages (final, rounds, heats as tables) of the events of one sport at one Games."""
    return rows("SELECT DISTINCT result_id, event_name FROM olympedia_event_rows WHERE games_id=:g AND sport_name=:s AND (:e IS NULL OR event_name=:e) ORDER BY event_name", g=games_id, s=sport, e=event)


@router.get("/match-board", tags=["pages"])
def match_board(games_id: str, sport: str, stage: Optional[str] = None, page_no: int = Query(1, alias="page"), page_size: int = Query(120, le=300)):
    """Matches of one sport at one Games with their labelled period / set scores (read from each saved match page's scoreboard table), for broadcast cards."""
    w = "WHERE games_id=:g AND sport_name=:s AND home_team IS NOT NULL AND (:st IS NULL OR LOWER(stage) LIKE :st)"
    p = dict(g=games_id, s=sport, st=f"%{stage.lower()}%" if stage else None)
    out = page(f"SELECT COUNT(*) FROM olympedia_matches {w}", f"SELECT result_id, games_id, sport_name, event_name, stage, match_date, location, home_team, home_noc, home_score, away_team, away_noc, away_score FROM olympedia_matches {w} ORDER BY event_name, match_date, result_id", page_no, page_size, **p)
    ids = [r["result_id"] for r in out["rows"]]
    by: dict = {}
    if ids:
        marks = ",".join(f":i{k}" for k in range(len(ids)))
        for t in rows(f"SELECT result_id, headers_json, rows_json FROM olympedia_match_tables WHERE kind='scoreboard' AND result_id IN ({marks})", **{f"i{k}": v for k, v in enumerate(ids)}):
            h, r = _loads(t["headers_json"]) or [], _loads(t["rows_json"]) or []
            if not r:
                continue
            i0 = h.index("NOC") + 1 if "NOC" in h else 3
            labels = [x for x in h[i0:] if x]
            by[t["result_id"]] = {"score_label": labels[0] if labels else None, "periods": [{"label": lab, "scores": [(_int(row[i0 + k]) if i0 + k < len(row) else None) for row in r[:2]]} for k, lab in enumerate(labels[1:], start=1)]}
    for r in out["rows"]:
        r.update(by.get(r["result_id"], {"score_label": None, "periods": []}))
    out["events"] = [r["event_name"] for r in rows("SELECT DISTINCT event_name FROM olympedia_matches WHERE games_id=:g AND sport_name=:s ORDER BY event_name", g=games_id, s=sport)]
    return out
