"""Olympedia-style platform API: edition event index, event results pages (every saved table, with real links), match / bout / heat pages with previous / next navigation,
medals by country with filters, a country at one edition (every result, medal or not), edition assets and data coverage.

Everything comes from the warehouse: olympedia_pages, olympedia_page_tables, olympedia_page_links (scripts/build_page_links.py), olympedia_athlete_xref,
olympedia_matches, olympedia_country_results, silver_medal_awards and games. Nothing is invented; a link is only returned when its target exists."""
from __future__ import annotations

import json
import zlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.platform import csv_response, one, rows

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]

# sports whose Olympedia 'Match' pages are team matches (scoreboard, line-ups); every other sport's match pages are individual bouts / duels
TEAM_SPORTS = {"Basketball", "3x3 Basketball", "Hockey", "Volleyball", "Beach Volleyball", "Curling", "Water Polo", "Handball", "Ice Hockey", "Football", "Baseball",
               "Rugby Sevens", "Softball", "Roller Hockey", "Basque pelota"}
MEDAL_CONVENTION = ("One medal per podium place per NOC per event, from the Olympedia results pages (a team or crew medal counts once; tied places each count). "
                    "Historical NOCs are kept as recorded and never merged: URS, EUN, RUS, ROC, OAR, AIN, GDR, FRG, EUA and GER are separate rows.")


def _loads(s, default=None):
    try:
        if isinstance(s, (bytes, memoryview)):  # slim deployment DB stores large JSON zlib-compressed
            s = zlib.decompress(bytes(s)).decode("utf-8")
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


def _crumbs(breadcrumb: str) -> list[str]:
    out: list[str] = []
    for x in (breadcrumb or "").split(" > "):
        if x and x not in out:
            out.append(x)
    return out


def _sport(breadcrumb: str) -> Optional[str]:
    parts = _crumbs(breadcrumb)
    i = next((k for k, p in enumerate(parts) if re.search(r"Olympics$|Olympic Games$", p)), None)
    return parts[i + 1] if i is not None and i + 1 < len(parts) else None


def gender_of(title: str) -> str:
    t = (title or "").split(" – ")[0]
    for g in ("Women", "Men", "Mixed", "Open"):
        if re.search(rf"\b{g}\b", t):
            return g
    return "Open"


def _num(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _edition(games_id: str) -> dict:
    g = one("SELECT games_id, year, season, host_city, official_edition_name FROM games WHERE games_id=:g", g=games_id)
    if not g:
        y, _, s = games_id.partition("_")
        g = {"games_id": games_id, "year": _num(y), "season": s, "host_city": None, "official_edition_name": None}
    g["name"] = f"{g['host_city']} {g['year']}" if g.get("host_city") else f"{g['year']} {str(g['season']).title()} Olympics"
    return g


def _seg(child_kind: Optional[str], sport: Optional[str]) -> Optional[str]:
    if child_kind == "matches":
        return "matches" if sport in TEAM_SPORTS else "bouts"
    if child_kind == "phases":
        return "heats"
    return None


def _top_event(result_id: str) -> Optional[dict]:
    """Walk up the link index to the event page that owns a match / heat / part page."""
    seen, cur = set(), result_id
    while cur and cur not in seen:
        seen.add(cur)
        p = one("SELECT result_id, kind, games_id, title, breadcrumb FROM olympedia_pages WHERE result_id=:r", r=cur)
        if p and p["kind"] == "events":
            return p
        up = one("SELECT parent_id FROM olympedia_page_links WHERE child_id=:r ORDER BY relation='table' DESC, CAST(parent_id AS INTEGER) LIMIT 1", r=cur)
        cur = up["parent_id"] if up else None
    return None


def _route(child_id: str, kind: Optional[str], games_id: str, event_id: str, sport: Optional[str]) -> Optional[str]:
    if kind == "events":
        return f"/games/{games_id}/events/{child_id}"
    seg = _seg(kind, sport)
    return f"/games/{games_id}/events/{event_id}/{seg}/{child_id}" if seg else None


def _annotate(tables: list[dict], games_id: str, event_id: str, sport: Optional[str]) -> list[dict]:
    """Give every link cell a route inside the app, only when its target exists (saved page / known athlete)."""
    ath_ids, res_ids = set(), set()
    for t in tables:
        for row in t["links"]:
            for cell in row or []:
                for x in cell or []:
                    if x.get("athletes"):
                        ath_ids.add(str(x["athletes"]))
                    if x.get("results"):
                        res_ids.add(str(x["results"]))
    xref, kinds = {}, {}
    ids = list(ath_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        ph = ",".join(f":a{k}" for k in range(len(chunk)))
        xref.update({r["olympedia_id"]: r["athlete_id"] for r in rows(f"SELECT olympedia_id, athlete_id FROM olympedia_athlete_xref WHERE olympedia_id IN ({ph})", **{f"a{k}": v for k, v in enumerate(chunk)})})
    ids = list(res_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        ph = ",".join(f":r{k}" for k in range(len(chunk)))
        kinds.update({r["result_id"]: r["kind"] for r in rows(f"SELECT result_id, kind FROM olympedia_pages WHERE result_id IN ({ph})", **{f"r{k}": v for k, v in enumerate(chunk)})})
    for t in tables:
        for row in t["links"]:
            for cell in row or []:
                for x in cell or []:
                    if x.get("athletes") and str(x["athletes"]) in xref:
                        x["route"] = f"/athletes/{xref[str(x['athletes'])]}"
                    elif x.get("results") and str(x["results"]) in kinds:
                        r = _route(str(x["results"]), kinds[str(x["results"])], games_id, event_id, sport)
                        if r:
                            x["route"] = r
                    elif x.get("countries"):
                        x["route"] = f"/countries/{x['countries']}/editions/{games_id}"
    return tables


def _tables(result_id: str) -> list[dict]:
    return [{"index": t["table_index"], "section": t["section"] or "", "headers": _loads(t["headers_json"], []), "rows": _loads(t["rows_json"], []), "links": _loads(t["links_json"], [])}
            for t in rows("SELECT table_index, section, headers_json, rows_json, links_json FROM olympedia_page_tables WHERE result_id=:r ORDER BY table_index", r=result_id)]


def _stages(tables: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for t in tables:
        sec = t["section"] or "Final standings"
        if sec not in out:
            out[sec] = {"label": sec, "tables": [], "kind": "matches" if any(str(h).lower() == "match" for h in t["headers"]) else "ranking"}
        out[sec]["tables"].append(t["index"])
    return list(out.values())


@lru_cache(maxsize=64)
def _event_index(games_id: str) -> tuple:
    pages = rows("SELECT result_id, title, breadcrumb, meta_json FROM olympedia_pages WHERE games_id=:g AND kind='events'", g=games_id)
    counts = {r["parent_id"]: r for r in rows("""SELECT parent_id, SUM(relation='table' AND child_kind='matches') matches, SUM(relation='table' AND child_kind='phases') heats,
                                                 SUM(relation!='table') parts FROM olympedia_page_links WHERE games_id=:g GROUP BY parent_id""", g=games_id)}
    medal_events = {r["result_id"] for r in rows("SELECT DISTINCT result_id FROM silver_medal_awards WHERE games_id=:g", g=games_id)}
    out = []
    for p in pages:
        m = _loads(p["meta_json"], {}) or {}
        c = counts.get(p["result_id"], {})
        out.append({"result_id": p["result_id"], "title": p["title"], "sport": _sport(p["breadcrumb"]) or "Other", "gender": gender_of(p["title"]), "date": m.get("Date"),
                    "status": m.get("Status"), "location": m.get("Location"), "participants": m.get("Participants"), "format": m.get("Format"),
                    "matches": c.get("matches") or 0, "heats": c.get("heats") or 0, "parts": c.get("parts") or 0, "has_medals": p["result_id"] in medal_events})
    out.sort(key=lambda e: (e["sport"], e["title"]))
    return tuple(out)


# ------------------------------------------------------------------ edition event index
@router.get("/games/{games_id}/events", tags=["olympic"])
def edition_events(games_id: str, sport: Optional[str] = None, gender: Optional[str] = None, q: Optional[str] = None):
    """Every event of one edition, grouped by sport, with real Olympedia result ids."""
    events = list(_event_index(games_id))
    if not events:
        raise HTTPException(404, "no saved events for this edition")
    allsports = sorted({e["sport"] for e in events})
    if sport:
        events = [e for e in events if e["sport"].lower() == sport.lower()]
    if gender:
        events = [e for e in events if e["gender"].lower() == gender.lower()]
    if q:
        words = q.lower().split()
        events = [e for e in events if all(w in (e["title"] + " " + e["sport"]).lower() for w in words)]
    groups: dict[str, list] = {}
    for e in events:
        groups.setdefault(e["sport"], []).append(e)
    return {"edition": _edition(games_id), "total": len(events), "all_sports": allsports, "genders": ["Men", "Women", "Mixed", "Open"],
            "sports": [{"sport": s, "events": v} for s, v in sorted(groups.items())]}


@router.get("/sports-by-edition", tags=["olympic"])
def sports_by_edition(season: Optional[str] = None):
    """For every held edition (optionally one season): its sports with their number of events, from the saved event index.
    The sport names are the ones /games/{id}/sports/{sport} accepts, so a pictogram links straight to that sport's events at that edition."""
    out = {}
    for g in rows("SELECT games_id FROM games WHERE year<=2026 AND (:s IS NULL OR season=:s) ORDER BY year", s=season.lower() if season else None):
        counts: dict[str, int] = {}
        for e in _event_index(g["games_id"]):
            counts[e["sport"]] = counts.get(e["sport"], 0) + 1
        out[g["games_id"]] = [{"sport": k, "events": v} for k, v in sorted(counts.items())]
    return out


@router.get("/games/{games_id}/sports/{sport}", tags=["olympic"])
def edition_sport(games_id: str, sport: str):
    return edition_events(games_id, sport=sport)


@router.get("/games/{games_id}/results", tags=["olympic"])
def edition_results(games_id: str):
    return edition_events(games_id)


# ------------------------------------------------------------------ event results page
def _page_payload(result_id: str) -> dict:
    p = one("SELECT result_id, games_id, kind, title, breadcrumb, meta_json, dropdowns_json FROM olympedia_pages WHERE result_id=:r", r=result_id)
    if not p:
        raise HTTPException(404, "page not saved")
    top = p if p["kind"] == "events" else (_top_event(result_id) or p)
    sport = _sport(p["breadcrumb"]) or _sport(top["breadcrumb"])
    g = p["games_id"]
    tables = _annotate(_tables(result_id), g, top["result_id"], sport)
    txt = one("SELECT description_json, section_meta_json FROM olympedia_page_text WHERE result_id=:r", r=result_id) or {}
    return {"description": _loads(txt.get("description_json"), []) or [], "section_meta": _loads(txt.get("section_meta_json"), {}) or {},"result_id": p["result_id"], "games_id": g, "kind": p["kind"], "title": p["title"], "sport": sport, "gender": gender_of(p["title"]),
            "edition": _edition(g), "meta": _loads(p["meta_json"], {}) or {}, "breadcrumb": _crumbs(p["breadcrumb"]),
            "event": {"result_id": top["result_id"], "title": top["title"]}, "tables": tables, "stages": _stages(tables),
            "source_url": f"https://www.olympedia.org/results/{result_id}"}


def _parts(result_id: str, games_id: str, event_id: str, sport: Optional[str]) -> list[dict]:
    """Sub-pages chosen from a dropdown on Olympedia (Parts, Standings after round n, Lift #n, Run #n ...), deduped, in id order."""
    seen, out = set(), []
    for r in rows("""SELECT child_id, label, relation, section, child_kind FROM olympedia_page_links WHERE parent_id=:r AND relation IN ('dropdown','standings')
                     ORDER BY CAST(child_id AS INTEGER)""", r=result_id):
        if r["child_id"] in seen:
            continue
        seen.add(r["child_id"])
        t = one("SELECT title FROM olympedia_pages WHERE result_id=:c", c=r["child_id"])
        label = (t["title"].split(" – ", 1)[1] if t and " – " in t["title"] else r["label"]) or r["child_id"]
        out.append({"result_id": r["child_id"], "label": label, "group": r["section"] if r["relation"] == "dropdown" else "Standings",
                    "route": _route(r["child_id"], r["child_kind"], games_id, event_id, sport)})
    return out


def _siblings(result_id: str, games_id: str, sport: Optional[str]) -> dict:
    ev = [e for e in _event_index(games_id) if e["sport"] == sport]
    ids = [e["result_id"] for e in ev]
    if result_id not in ids:
        return {"prev": None, "next": None}
    i = ids.index(result_id)
    pick = lambda e: {"result_id": e["result_id"], "title": e["title"], "route": f"/games/{games_id}/events/{e['result_id']}"} if e else None
    return {"prev": pick(ev[i - 1] if i > 0 else None), "next": pick(ev[i + 1] if i + 1 < len(ev) else None)}


@router.get("/events/{result_id}", tags=["olympic"])
def event_page(result_id: str):
    """One event results page as on Olympedia: header facts, every table (stage by stage) with links to athletes, countries and each match / bout / heat page."""
    d = _page_payload(result_id)
    d["parts"] = _parts(result_id, d["games_id"], d["event"]["result_id"], d["sport"])
    d["team_sport"] = d["sport"] in TEAM_SPORTS
    d["siblings"] = _siblings(result_id, d["games_id"], d["sport"])
    d["medals"] = rows("SELECT medal_type AS medal, noc_code AS noc FROM silver_medal_awards WHERE result_id=:r ORDER BY CASE medal_type WHEN 'Gold' THEN 1 WHEN 'Silver' THEN 2 ELSE 3 END, noc_code", r=result_id)
    d["counts"] = one("""SELECT SUM(relation='table' AND child_kind='matches') matches, SUM(relation='table' AND child_kind='phases') heats, COUNT(*) links
                         FROM olympedia_page_links WHERE parent_id=:r""", r=result_id)
    return d


@router.get("/events/{result_id}/stages", tags=["olympic"])
def event_stages(result_id: str):
    d = event_page(result_id)
    return {"stages": d["stages"], "parts": d["parts"]}


@router.get("/events/{result_id}/results", tags=["olympic"])
def event_results(result_id: str):
    d = _page_payload(result_id)
    return {"title": d["title"], "tables": [t for t in d["tables"] if any(str(h).lower() == "pos" for h in t["headers"])]}


@router.get("/events/{result_id}/standings", tags=["olympic"])
def event_standings(result_id: str):
    d = _page_payload(result_id)
    tabs = [t for t in d["tables"] if re.search(r"round-robin|group|pool|standing", t["section"], re.I) and not any(str(h).lower() == "match" for h in t["headers"])]
    return {"title": d["title"], "tables": tabs, "parts": [p for p in _parts(result_id, d["games_id"], d["event"]["result_id"], d["sport"]) if p["group"] == "Standings"]}


# ------------------------------------------------------------------ match / bout / heat pages
def _subpage(result_id: str, want: Optional[str] = None) -> dict:
    d = _page_payload(result_id)
    if d["kind"] == "events":
        raise HTTPException(404, "this id is an event page, not a match / bout / heat")
    up = one("SELECT parent_id, relation, section, table_index FROM olympedia_page_links WHERE child_id=:r ORDER BY relation='table' DESC, CAST(parent_id AS INTEGER) LIMIT 1", r=result_id)
    nav = {"prev": None, "next": None, "index": None, "count": None, "section": None, "parent": None}
    if up:
        sibs = rows("""SELECT child_id, label, section, child_kind FROM olympedia_page_links WHERE parent_id=:p AND relation=:rel
                       ORDER BY COALESCE(table_index, 0), COALESCE(row_index, 0), CAST(child_id AS INTEGER)""", p=up["parent_id"], rel=up["relation"])
        uniq, seen = [], set()
        for s in sibs:
            if s["child_id"] not in seen:
                seen.add(s["child_id"])
                uniq.append(s)
        ids = [s["child_id"] for s in uniq]
        i = ids.index(result_id) if result_id in ids else None
        mk = lambda s: {"result_id": s["child_id"], "label": f"{s['section'] + ' · ' if s['section'] and not str(s['section']).startswith('sub_select') else ''}{s['label']}",
                        "route": _route(s["child_id"], s["child_kind"], d["games_id"], d["event"]["result_id"], d["sport"])} if s else None
        parent = one("SELECT result_id, kind, title FROM olympedia_pages WHERE result_id=:p", p=up["parent_id"])
        nav = {"prev": mk(uniq[i - 1]) if i else None, "next": mk(uniq[i + 1]) if i is not None and i + 1 < len(uniq) else None,
               "index": (i + 1) if i is not None else None, "count": len(uniq), "section": up["section"] if up["relation"] == "table" else None,
               "parent": {"result_id": parent["result_id"], "title": parent["title"], "kind": parent["kind"],
                          "route": f"/games/{d['games_id']}/events/{parent['result_id']}" if parent["kind"] == "events" else _route(parent["result_id"], parent["kind"], d["games_id"], d["event"]["result_id"], d["sport"])} if parent else None}
    d["nav"] = nav
    d["type"] = _seg(d["kind"], d["sport"])
    d["parts"] = _parts(result_id, d["games_id"], d["event"]["result_id"], d["sport"])
    m = one("SELECT label, stage, home_team, home_noc, home_score, away_team, away_noc, away_score FROM olympedia_matches WHERE result_id=:r", r=result_id)
    d["match"] = m
    d["has_scoreboard"] = bool(m and m["home_team"] and d["sport"] in TEAM_SPORTS)
    return d


@router.get("/subpages/{result_id}", tags=["olympic"])
def subpage(result_id: str):
    """A match, bout, heat or part page: every saved table, the owning event, and previous / next in the same table or dropdown."""
    return _subpage(result_id)


@router.get("/bouts/{result_id}", tags=["olympic"])
def bout_page(result_id: str):
    return _subpage(result_id)


@router.get("/heats/{result_id}", tags=["olympic"])
def heat_page(result_id: str):
    return _subpage(result_id)


# ------------------------------------------------------------------ medals by country
def _medal_rows(season, year_from, year_to, games_id, noc, sport, gender, medal):
    w, p = ["1=1"], {}
    if season:
        w.append("g.season=:season"); p["season"] = season.lower()
    if year_from:
        w.append("g.year>=:yf"); p["yf"] = year_from
    if year_to:
        w.append("g.year<=:yt"); p["yt"] = year_to
    if games_id:
        w.append("m.games_id=:g"); p["g"] = games_id
    if noc:
        w.append("m.noc_code=:noc"); p["noc"] = noc.upper()
    if sport:
        w.append("m.sport_name=:sp"); p["sp"] = sport
    if medal:
        w.append("m.medal_type=:md"); p["md"] = medal.title()
    data = rows(f"""SELECT m.noc_code, m.games_id, m.sport_name, m.event_name, m.medal_type FROM silver_medal_awards m JOIN games g ON g.games_id=m.games_id WHERE {' AND '.join(w)}""", **p)
    if gender:
        data = [r for r in data if gender_of(r["event_name"]).lower() == gender.lower()]
    return data


@lru_cache(maxsize=1)
def _noc_names() -> dict:
    return {r["noc_code"]: r["historical_name"] for r in rows("SELECT noc_code, historical_name FROM gold_country_participation_history")}


@lru_cache(maxsize=256)
def _appearances(season, year_from, year_to, games_id) -> dict:
    w, p = ["1=1"], {}
    if season:
        w.append("season=:s"); p["s"] = season.lower()
    if year_from:
        w.append("year>=:yf"); p["yf"] = year_from
    if year_to:
        w.append("year<=:yt"); p["yt"] = year_to
    if games_id:
        w.append("games_id=:g"); p["g"] = games_id
    return {r["noc_code"]: r["n"] for r in rows("SELECT noc_code, COUNT(DISTINCT games_id) n FROM silver_participations WHERE " + " AND ".join(w) + " GROUP BY noc_code", **p)}


@router.get("/medals/countries", tags=["olympic"])
def medals_by_country(season: Optional[str] = None, year_from: Optional[int] = None, year_to: Optional[int] = None, games_id: Optional[str] = None, noc: Optional[str] = None,
                      sport: Optional[str] = None, gender: Optional[str] = None, medal: Optional[str] = None, sort: str = "gold", order: str = "desc",
                      q: Optional[str] = None, include_all: bool = False,
                      page_no: int = Query(1, alias="page"), page_size: int = Query(50, le=500), format: Optional[str] = None):
    """Medal table by NOC with filters (season, year range, edition, NOC, sport, gender, medal, name search). Ties in G/S/B share a rank.
    `appearances` = editions the NOC took part in within the season / year / edition filter (silver_participations). With include_all, NOCs that took part
    without winning a medal are listed too (zero medals, numbered after the medal winners by appearances) - only when no sport / gender / medal filter narrows the table to medals."""
    data = _medal_rows(season, year_from, year_to, games_id, noc, sport, gender, medal)
    agg: dict[str, dict] = {}
    names = _noc_names()
    for r in data:
        a = agg.setdefault(r["noc_code"], {"noc": r["noc_code"], "country": names.get(r["noc_code"], r["noc_code"]), "gold": 0, "silver": 0, "bronze": 0, "total": 0, "editions": set(), "sports": set()})
        a[r["medal_type"].lower()] += 1
        a["total"] += 1
        a["editions"].add(r["games_id"])
        a["sports"].add(r["sport_name"])
    out = [{**a, "editions": len(a["editions"]), "sports": len(a["sports"])} for a in agg.values()]
    out.sort(key=lambda a: (-a["gold"], -a["silver"], -a["bronze"], a["noc"]))
    rank, prev = 0, None
    for i, a in enumerate(out):
        key = (a["gold"], a["silver"], a["bronze"])
        if key != prev:
            rank, prev = i + 1, key
        a["rank"] = rank
    app = _appearances(season, year_from, year_to, games_id)
    for a in out:
        a["appearances"] = app.get(a["noc"], 0)
    if include_all and not (sport or gender or medal):
        have = {a["noc"] for a in out}
        # NOCs without a medal continue the numbering after the medal winners: most appearances first, then by name
        start = len(out) + 1
        rest = sorted(((k, v) for k, v in app.items() if k not in have and (not noc or k == noc.upper())), key=lambda kv: (-kv[1], names.get(kv[0], kv[0])))
        out += [{"noc": k, "country": names.get(k, k), "gold": 0, "silver": 0, "bronze": 0, "total": 0, "editions": 0, "sports": 0, "rank": start + i, "appearances": v}
                for i, (k, v) in enumerate(rest)]
    if q:
        ql = q.strip().lower()
        out = [a for a in out if ql in a["noc"].lower() or ql in str(a["country"]).lower()]
    if sort == "rank":
        out.sort(key=lambda a: (a["rank"] is None, a["rank"] or 0, a["noc"]))
        if order == "desc":
            out.reverse()
    elif sort in ("silver", "bronze", "total", "editions", "sports", "noc", "country", "appearances"):
        out.sort(key=lambda a: (a[sort], -(a["gold"])) if sort not in ("noc", "country") else a[sort], reverse=(order == "desc"))
    elif order == "asc":
        out.reverse()
    if format == "csv":
        return csv_response(out, "medals_by_country")
    totals = {k: sum(a[k] for a in out) for k in ("gold", "silver", "bronze", "total")}
    start = (max(page_no, 1) - 1) * page_size
    return {"total": len(out), "page": page_no, "page_size": page_size, "rows": out[start:start + page_size], "totals": totals, "convention": MEDAL_CONVENTION,
            "sports": sorted({r["sport_name"] for r in data}) if not sport else [sport]}


@router.get("/medals/editions/{games_id}", tags=["olympic"])
def medals_edition(games_id: str, sport: Optional[str] = None, gender: Optional[str] = None, page_size: int = Query(300, le=500)):
    d = medals_by_country(games_id=games_id, sport=sport, gender=gender, page_size=page_size)
    d["edition"] = _edition(games_id)
    d["all_sports"] = sorted({r["sport_name"] for r in rows("SELECT DISTINCT sport_name FROM silver_medal_awards WHERE games_id=:g", g=games_id)})
    return d


# ------------------------------------------------------------------ a country at one edition
def status_of(position: str) -> str:
    p = (position or "").strip()
    m = re.match(r"^(DNF|DNS|DQ|DSQ|AC|NM|NP|DNQ|WD|NR|NC|DQB|TNP|NH)\b", p, re.I)
    if m:
        return m.group(1).upper()
    return "Ranked" if re.match(r"^=?\d", p) else ("—" if not p else "Other")


@router.get("/countries/{noc}/editions", tags=["olympic"])
def country_editions(noc: str):
    data = rows("""SELECT r.games_id, COUNT(*) entries, COUNT(DISTINCT r.event) events, COUNT(DISTINCT r.athlete_id) athletes FROM olympedia_country_results r WHERE r.noc=:n GROUP BY r.games_id ORDER BY r.games_id""", n=noc.upper())
    med = {r["games_id"]: r for r in rows("""SELECT games_id, SUM(medal_type='Gold') gold, SUM(medal_type='Silver') silver, SUM(medal_type='Bronze') bronze FROM silver_medal_awards WHERE noc_code=:n GROUP BY games_id""", n=noc.upper())}
    for d in data:
        d.update({k: (med.get(d["games_id"]) or {}).get(k) or 0 for k in ("gold", "silver", "bronze")})
        d["edition"] = _edition(d["games_id"])
    data.sort(key=lambda d: (d["edition"]["year"], d["edition"]["season"]))
    return {"noc": noc.upper(), "country": _noc_names().get(noc.upper(), noc.upper()), "editions": data}


@router.get("/countries/{noc}/olympedia/{games_id}", tags=["olympic"])
def country_olympedia_edition(noc: str, games_id: str):
    """The NOC's saved Olympedia page for one edition (olympedia.org/countries/{NOC}/editions/{id}) - the full table as published:
    '#Sport' heading rows, event rows (event, athlete / team, place, medal) and team-member rows - with in-app routes added to its links
    (event -> results page, athlete -> profile) wherever the target exists."""
    from backend.api.pages import country_at_games
    d = country_at_games(noc, games_id)
    tables = [{**t, "section": t["section"] or "", "headers": t["headers"] or [], "links": t["links"] or []} for t in d["tables"]]
    d["tables"] = _annotate(tables, games_id, "", None)
    d["edition"] = _edition(games_id)
    d["editions"] = [{"games_id": r["games_id"], "name": _edition(r["games_id"])["name"], "year": r["year"], "season": r["season"]}
                     for r in rows("""SELECT p.games_id, g.year, g.season FROM olympedia_country_pages p JOIN games g USING(games_id)
                                      WHERE p.noc=:n AND p.page_kind='country_edition' ORDER BY g.year DESC, g.season""", n=noc.upper())]
    return d


@router.get("/countries/{noc}/olympedia-editions", tags=["olympic"])
def country_olympedia_editions(noc: str):
    """Editions for which the NOC's Olympedia edition page is saved (newest first) - the choices of the Results edition selector."""
    return [{"games_id": r["games_id"], "name": _edition(r["games_id"])["name"], "year": r["year"], "season": r["season"]}
            for r in rows("""SELECT p.games_id, g.year, g.season FROM olympedia_country_pages p JOIN games g USING(games_id)
                             WHERE p.noc=:n AND p.page_kind='country_edition' ORDER BY g.year DESC, g.season""", n=noc.upper())]


@router.get("/countries/{noc}/results", tags=["olympic"])
def country_results(noc: str, format: Optional[str] = None):
    """Every Olympedia entry of one NOC across all editions (medal or not): edition, sport, event, gender, athlete / team, place, status, medal and - where the
    saved results table lists it - the result with its column name. Missing results stay null, never estimated."""
    noc = noc.upper()
    match = "e.result_id=r.result_id AND e.is_main=1 AND (e.competitor=r.athlete OR (e.noc=r.noc AND e.position=r.position))"
    data = rows(f"""SELECT r.games_id, g.year, g.season, r.sport, r.event, r.result_id, r.athlete, r.position, r.medal, x.athlete_id AS warehouse_id,
                     (SELECT e.result_text FROM olympedia_event_rows e WHERE {match} LIMIT 1) AS result,
                     (SELECT e.result_header FROM olympedia_event_rows e WHERE {match} LIMIT 1) AS result_type
                   FROM olympedia_country_results r JOIN games g ON g.games_id=r.games_id LEFT JOIN olympedia_athlete_xref x ON x.olympedia_id=r.athlete_id
                   WHERE r.noc=:n ORDER BY g.year, g.season, r.sport, r.event""", n=noc)
    if not data:
        raise HTTPException(404, "no results saved for this NOC")
    saved = {r["result_id"] for r in rows("SELECT result_id FROM olympedia_pages WHERE kind='events' AND result_id IN (SELECT DISTINCT result_id FROM olympedia_country_results WHERE noc=:n)", n=noc)}
    names = {}
    out = []
    for r in data:
        if r["games_id"] not in names:
            names[r["games_id"]] = _edition(r["games_id"])["name"]
        out.append({"games_id": r["games_id"], "year": r["year"], "season": r["season"], "edition": names[r["games_id"]], "sport": r["sport"], "event": r["event"], "gender": gender_of(r["event"]),
                    "athlete": r["athlete"], "athlete_route": f"/athletes/{r['warehouse_id']}" if r["warehouse_id"] else None,
                    "event_route": f"/games/{r['games_id']}/events/{r['result_id']}" if r["result_id"] in saved else None,
                    "position": r["position"] or None, "status": status_of(r["position"]), "medal": r["medal"] or None, "result": r["result"], "result_type": r["result_type"]})
    if format == "csv":
        return csv_response(out, f"{noc}_results")
    return {"noc": noc, "country": _noc_names().get(noc, noc), "total": len(out), "rows": out}


@router.get("/countries/{noc}/editions/{games_id}", tags=["olympic"])
def country_edition(noc: str, games_id: str):
    """Every entry of one NOC at one edition (medal or not), grouped sport -> event -> athletes, with the place or status as Olympedia lists it."""
    noc = noc.upper()
    data = rows("""SELECT r.sport, r.event, r.result_id, r.athlete, r.athlete_id, r.position, r.medal, x.athlete_id AS warehouse_id
                   FROM olympedia_country_results r LEFT JOIN olympedia_athlete_xref x ON x.olympedia_id=r.athlete_id WHERE r.noc=:n AND r.games_id=:g""", n=noc, g=games_id)
    if not data:
        raise HTTPException(404, "no results saved for this NOC at this edition")
    saved = {r["result_id"] for r in rows("SELECT result_id FROM olympedia_pages WHERE games_id=:g AND kind='events'", g=games_id)}
    sports: dict[str, dict] = {}
    for r in data:
        ev = sports.setdefault(r["sport"], {}).setdefault(r["event"], {"event": r["event"], "result_id": r["result_id"], "gender": gender_of(r["event"]),
                                                                      "route": f"/games/{games_id}/events/{r['result_id']}" if r["result_id"] in saved else None, "entries": []})
        ev["entries"].append({"athlete": r["athlete"], "olympedia_id": r["athlete_id"], "route": f"/athletes/{r['warehouse_id']}" if r["warehouse_id"] else None,
                              "position": r["position"], "status": status_of(r["position"]), "medal": r["medal"] or None})
    med = rows("SELECT medal_type, COUNT(*) n FROM silver_medal_awards WHERE noc_code=:n AND games_id=:g GROUP BY medal_type", n=noc, g=games_id)
    mc = {m["medal_type"].lower(): m["n"] for m in med}
    out = [{"sport": s, "events": sorted(evs.values(), key=lambda e: e["event"])} for s, evs in sorted(sports.items())]
    return {"noc": noc, "country": _noc_names().get(noc, noc), "edition": _edition(games_id),
            "summary": {"entries": len(data), "athletes": len({r["athlete_id"] for r in data}), "events": len({r["result_id"] for r in data}), "sports": len(sports),
                        "gold": mc.get("gold", 0), "silver": mc.get("silver", 0), "bronze": mc.get("bronze", 0),
                        "non_medal_entries": sum(1 for r in data if not r["medal"])},
            "sports": out, "convention": "Entries are athlete rows of the Olympedia country page (a team member is one entry each). Medal counts use the medal-table convention: " + MEDAL_CONVENTION}


# ------------------------------------------------------------------ edition participants and gender breakdown
@router.get("/games/{games_id}/participants", tags=["olympic"])
def edition_participants(games_id: str, format: Optional[str] = None):
    """Every athlete entry of one edition (one row per athlete per event), medal winners or not, from silver_participations joined to athletes."""
    data = rows("""SELECT p.athlete_id, COALESCE(a.full_name, 'Athlete ' || p.athlete_id) athlete, p.noc_code noc, p.sport_name sport, p.event_name event, p.gender, p.age, p.medal
                   FROM silver_participations p LEFT JOIN athletes a USING(athlete_id) WHERE p.games_id=:g ORDER BY p.noc_code, athlete, p.event_name""", g=games_id)
    if not data and not one("SELECT 1 FROM games WHERE games_id=:g AND year<=2026", g=games_id):
        raise HTTPException(404, "no participants for this edition")
    # each entry's event -> its results page, when the event name matches a saved Olympedia event of the same sport (exact after normalising; never guessed)
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", str(s).lower().replace("×", "x"))
    idx = {(e["sport"], norm(e["title"])): e["result_id"] for e in _event_index(games_id)}
    def flip(name: str) -> str:   # "Men's Middleweight, Freestyle" -> "Middleweight, Freestyle, Men" (older source naming)
        m = re.match(r"^(Men|Women|Mixed)'?s?\s+(.*)$", name.strip())
        return f"{m.group(2)}, {m.group(1)}" if m else name
    for r in data:
        ev = str(r["event"] or "")
        ev = ev[len(r["sport"]):].strip() if ev.startswith(str(r["sport"])) else ev
        rid = idx.get((r["sport"], norm(ev))) or idx.get((r["sport"], norm(flip(ev))))
        r["event_route"] = f"/games/{games_id}/events/{rid}" if rid else None
    if format == "csv":
        return csv_response(data, f"{games_id}_participants")
    return {"games_id": games_id, "total": len(data), "athletes": len({r["athlete_id"] for r in data}), "rows": data}


@router.get("/games/{games_id}/gender", tags=["olympic"])
def edition_gender(games_id: str):
    """Distinct athletes by gender at one edition: overall, by sport, by event and by NOC (silver_participations), plus the progression of the same season."""
    season = (one("SELECT season FROM games WHERE games_id=:g", g=games_id) or {}).get("season")
    piv = lambda col: f"""SELECT {col} name, COUNT(DISTINCT CASE WHEN gender='M' THEN athlete_id END) men, COUNT(DISTINCT CASE WHEN gender='F' THEN athlete_id END) women,
                          COUNT(DISTINCT athlete_id) total FROM silver_participations WHERE games_id=:g GROUP BY {col} ORDER BY total DESC, name"""
    overall = one("""SELECT COUNT(DISTINCT CASE WHEN gender='M' THEN athlete_id END) men, COUNT(DISTINCT CASE WHEN gender='F' THEN athlete_id END) women,
                     COUNT(DISTINCT athlete_id) total FROM silver_participations WHERE games_id=:g""", g=games_id)
    overall["unrecorded"] = overall["total"] - overall["men"] - overall["women"]   # athletes whose gender the source does not record (shown, never guessed)
    return {"overall": overall,
            "by_sport": rows(piv("sport_name"), g=games_id), "by_event": rows(piv("event_name"), g=games_id), "by_noc": rows(piv("noc_code"), g=games_id),
            "progression": rows("SELECT games_id, year, male_athletes men, female_athletes women, female_share FROM gold_edition_performance WHERE season=:s ORDER BY year", s=season)}


# ------------------------------------------------------------------ assets and coverage
@router.get("/assets/editions/{games_id}", tags=["olympic"])
def edition_assets(games_id: str):
    # the serverless bundle ships a copy next to this module (deploy/vercel-api/prepare.py)
    f = next((p for p in (ROOT / "frontend/public/assets/editions.json", Path(__file__).with_name("editions.json")) if p.exists()), None)
    reg = (_loads(f.read_text(encoding="utf-8"), {}) or {}) if f else {}
    e = (reg.get("editions") or {}).get(games_id)
    if not e:
        raise HTTPException(404, "edition not in the asset registry")
    return e


@lru_cache(maxsize=1)
def _coverage() -> list[dict]:
    q = lambda sql: {r["games_id"]: r for r in rows(sql)}
    pages = q("SELECT games_id, SUM(kind='events') events, SUM(kind='phases') phases, SUM(kind='matches') matches FROM olympedia_pages GROUP BY games_id")
    tabs = q("SELECT games_id, COUNT(*) tables FROM olympedia_page_tables GROUP BY games_id")
    links = q("SELECT games_id, COUNT(*) links, SUM(child_saved) links_saved FROM olympedia_page_links GROUP BY games_id")
    cr = q("SELECT games_id, COUNT(*) country_rows FROM olympedia_country_results GROUP BY games_id")
    med = q("SELECT games_id, COUNT(*) medals FROM silver_medal_awards GROUP BY games_id")
    games = rows("SELECT games_id, year, season, total_events FROM games WHERE year<=2026 ORDER BY year, season")
    out = []
    for g in games:
        gid = g["games_id"]
        row = {"games_id": gid, "year": g["year"], "season": g["season"], "official_events": g["total_events"]}
        for src in (pages, tabs, links, cr, med):
            row.update({k: v for k, v in (src.get(gid) or {}).items() if k != "games_id"})
        row["event_coverage"] = round((row.get("events") or 0) / g["total_events"], 3) if g["total_events"] else None
        out.append(row)
    return out


@router.get("/data-quality/coverage", tags=["olympic"])
def coverage():
    """Per edition: saved event / phase / match pages, tables, sub-page links (and how many resolve to a saved page), country rows, medals, and events saved vs official."""
    return {"editions": _coverage(), "note": "official_events comes from the games table (Wikipedia edition pages); events = saved Olympedia event pages. A ratio above 1 means Olympedia lists more event pages (e.g. separate pages per discipline)."}
