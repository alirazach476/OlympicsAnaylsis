"""Edition-by-edition warehouse completeness report."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, text

from backend.collectors.editions import all_editions
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS

e = create_engine("sqlite+pysqlite:///./data/olympics_warehouse.db")

queries = {
    "athletes_participations": """
        select games_id, count(*) c from athlete_participations group by 1
    """,
    "event_results": """
        select games_id, count(*) c from event_results group by 1
    """,
    "medals": """
        select games_id, count(*) c from medals group by 1
    """,
    "medal_tables_verified": """
        select games_id, count(*) c from medal_tables
        where table_scope='wikipedia_country_medal_table' group by 1
    """,
    "events": """
        select games_id, count(*) c from events group by 1
    """,
    "matches": """
        select games_id, count(*) c from matches group by 1
    """,
    "teams": """
        select games_id, count(*) c from teams group by 1
    """,
    "team_members": """
        select t.games_id, count(*) c from team_members tm
        join teams t on t.team_id = tm.team_id group by 1
    """,
    "match_results": """
        select m.games_id, count(*) c from match_results mr
        join matches m on m.match_id = mr.match_id group by 1
    """,
}


def to_map(rows):
    return {r[0]: int(r[1]) for r in rows}


with e.connect() as c:
    maps = {k: to_map(c.execute(text(q)).fetchall()) for k, q in queries.items()}
    # football-ish matches
    fb = to_map(
        c.execute(
            text(
                """
                select m.games_id, count(*) c
                from matches m
                join sports s on s.sport_id = m.sport_id
                where lower(s.sport_name) like '%football%'
                   or lower(s.sport_name) like '%soccer%'
                group by 1
                """
            )
        ).fetchall()
    )
    sports_by_games = {}
    # sports count via event_results
    for row in c.execute(
        text(
            """
            select games_id, count(distinct sport_id) c
            from event_results where sport_id is not null group by 1
            """
        )
    ):
        sports_by_games[row[0]] = int(row[1])

oly_root = Path("data/raw/olympedia/editions")
wiki_root = Path("data/raw/wikipedia/edition_graph")


def oly_counts(games_id: str):
    d = oly_root / games_id
    if not d.exists():
        return {"catalog": 0, "event_json": 0, "match_json": 0}
    catalog = 0
    cp = d / "events_catalog.json"
    if cp.exists():
        try:
            catalog = len(json.loads(cp.read_text(encoding="utf-8")))
        except Exception:
            catalog = 0
    return {
        "catalog": catalog,
        "event_json": len(list((d / "events").glob("*.json"))) if (d / "events").exists() else 0,
        "match_json": len(list((d / "matches").glob("*.json"))) if (d / "matches").exists() else 0,
    }


def wiki_graph(games_id: str):
    p = wiki_root / games_id
    if not p.exists():
        return {"sports": 0, "countries": 0, "calendar": False, "football_raw": False}
    sports = len(list((p / "sports").glob("*.json"))) if (p / "sports").exists() else 0
    countries = len(list((p / "countries").glob("*.json"))) if (p / "countries").exists() else 0
    # football raw elsewhere
    fb_dir = Path("data/raw/wikipedia/football")
    football_raw = False
    if fb_dir.exists():
        football_raw = any(games_id in x.name or str(games_id.split("_")[0]) in x.name for x in fb_dir.rglob("*"))
    return {
        "sports": sports,
        "countries": countries,
        "calendar": (p / "graph.json").exists() or (p / "edition_graph.json").exists(),
        "football_raw": football_raw,
    }


rows = []
for ed in all_editions():
    g = ed.games_id
    players = maps["athletes_participations"].get(g, 0)
    results = maps["event_results"].get(g, 0)
    medals = maps["medals"].get(g, 0)
    mt = maps["medal_tables_verified"].get(g, 0)
    events = maps["events"].get(g, 0)
    matches = maps["matches"].get(g, 0)
    teams = maps["teams"].get(g, 0)
    members = maps["team_members"].get(g, 0)
    mr = maps["match_results"].get(g, 0)
    football = fb.get(g, 0)
    oly = oly_counts(g)
    wg = wiki_graph(g)

    # completeness flags (honest thresholds)
    has_players = players > 0
    has_results = results > 0
    has_medal_table = mt > 0
    has_matches = matches > 0
    # summer football expected for modern games; winter ice hockey often has matches
    season = ed.season
    expect_team_fixtures = True  # all editions have some team sports historically after 1960

    missing = []
    if not has_players:
        missing.append("players")
    if not has_results:
        missing.append("event_results")
    if not has_medal_table:
        missing.append("verified_medal_table")
    if not has_matches:
        missing.append("matches/fixtures")
    if has_matches and members == 0:
        missing.append("squads/team_members")
    if season == "summer" and football == 0:
        missing.append("football_matches")
    if oly["catalog"] == 0:
        missing.append("olympedia_catalog")
    # olympedia team scrape incomplete if catalog exists but few matches for summer with many team sports
    if season == "summer" and oly["match_json"] < 20 and g >= "1960":
        if "matches/fixtures" not in missing and oly["match_json"] == 0:
            pass

    if not missing:
        status = "COMPLETE_CORE"
    elif has_players and has_results and has_medal_table and not has_matches:
        status = "PLAYERS+RESULTS+MEDALS — missing fixtures"
    elif has_players and has_results and not has_medal_table:
        status = "PLAYERS+RESULTS — medal table/fixtures gaps"
    elif has_players and has_results:
        status = "PARTIAL"
    else:
        status = "INCOMPLETE"

    rows.append(
        {
            "games_id": g,
            "season": season,
            "year": ed.year,
            "status": status,
            "players": players,
            "event_results": results,
            "events": events,
            "sports": sports_by_games.get(g, 0),
            "medals": medals,
            "verified_medal_table_rows": mt,
            "matches": matches,
            "match_results": mr,
            "football_matches": football,
            "teams": teams,
            "team_members_squads": members,
            "olympedia_catalog_events": oly["catalog"],
            "olympedia_match_json": oly["match_json"],
            "wiki_sport_pages": wg["sports"],
            "wiki_country_pages": wg["countries"],
            "missing": missing,
        }
    )

out = {
    "summary": {
        "editions": len(rows),
        "with_players": sum(1 for r in rows if r["players"] > 0),
        "with_event_results": sum(1 for r in rows if r["event_results"] > 0),
        "with_verified_medal_table": sum(1 for r in rows if r["verified_medal_table_rows"] > 0),
        "with_matches": sum(1 for r in rows if r["matches"] > 0),
        "with_squads": sum(1 for r in rows if r["team_members_squads"] > 0),
        "with_football_matches": sum(1 for r in rows if r["football_matches"] > 0),
        "total_matches": sum(r["matches"] for r in rows),
        "total_players_participations": sum(r["players"] for r in rows),
        "total_event_results": sum(r["event_results"] for r in rows),
    },
    "editions": rows,
}
Path("data/exports/edition_completeness.json").parent.mkdir(parents=True, exist_ok=True)
Path("data/exports/edition_completeness.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out["summary"], indent=2))
print("---")
for r in rows:
    miss = ",".join(r["missing"]) if r["missing"] else "-"
    print(
        f"{r['games_id']:14} players={r['players']:5} results={r['event_results']:5} "
        f"medal_tbl={r['verified_medal_table_rows']:3} matches={r['matches']:4} "
        f"fb={r['football_matches']:3} squads={r['team_members_squads']:4} "
        f"oly_m={r['olympedia_match_json']:4} | {r['status']} | missing: {miss}"
    )
