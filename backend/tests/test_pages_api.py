"""The page endpoints behind the redesigned UI: saved Olympedia pages as they appear, bouts, global search, a country at one Games."""
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_saved_page_keeps_every_table_of_the_100m_page():
    d = client.get("/api/pages/65310").json()
    assert d["title"] == "100 metres, Men"
    sections = [t["section"] for t in d["tables"]]
    assert "Round One" in sections and any(s.startswith("Heat") for s in sections)
    heat = next(t for t in d["tables"] if t["section"].startswith("Heat"))
    assert heat["headers"][:4] == ["Pos", "Lane", "Competitor", "NOC"]
    assert len(d["tables"]) >= 20


def test_judo_bout_page_has_match_result_and_winning_techniques():
    d = client.get("/api/pages/16094").json()
    flat = [r for t in d["tables"] for r in t["rows"]]
    assert ["Match Result", "Ippon"] in flat
    assert any(t["section"] == "Winning Techniques" and t["rows"][0][3] == "Kansetsu-juji-gatame" for t in d["tables"])


def test_wrestling_bout_keeps_decision_score():
    d = client.get("/api/pages/129322").json()
    assert ["Match Result", "Decision (8-7)"] in [r for t in d["tables"] for r in t["rows"]]


def test_breadcrumb_has_no_repeated_items():
    parts = client.get("/api/pages/105643").json()["breadcrumb"].split(" > ")
    assert len(parts) == len(set(parts))


def test_unknown_page_is_404():
    assert client.get("/api/pages/999999999").status_code == 404


def test_fencing_bouts_carry_touches():
    d = client.get("/api/bouts", params={"games_id": "1984_summer", "sport": "Fencing", "page_size": 5}).json()
    assert d["total"] > 1000 and "Foil, Individual, Men" in d["events"]
    two = d["rows"][0]["participants"]
    assert len(two) == 2 and two[0]["extra"]["touches delivered"] == "5"


def test_search_finds_edition_country_sport_and_athlete():
    assert client.get("/api/search", params={"q": "paris"}).json()["editions"][0]["games_id"] == "2024_summer"
    assert any(c["noc_code"] == "GER" for c in client.get("/api/search", params={"q": "germany"}).json()["countries"])
    assert any("Bolt" in a["full_name"] for a in client.get("/api/search", params={"q": "usain bolt"}).json()["athletes"])
    assert client.get("/api/search", params={"q": "x"}).status_code == 422


def test_country_at_games_is_the_olympedia_country_page():
    d = client.get("/api/countries/GER/at/1960_winter").json()
    assert d["title"] == "Germany at the 1960 Winter Olympics"
    assert ["Downhill, Men", "Hanspeter Lanig", "2", "Silver"] in d["tables"][0]["rows"]


@pytest.mark.parametrize("noc,games", [("XXX", "1960_winter"), ("GER", "1900_summer")])
def test_country_at_games_unknown_is_404(noc, games):
    assert client.get(f"/api/countries/{noc}/at/{games}").status_code == 404


def test_matches_expose_result_id_for_the_drawer():
    row = client.get("/api/matches", params={"sport": "Football", "games_id": "2024_summer", "page_size": 1}).json()["rows"][0]
    assert row["result_id"]


# ------------------------------------------------------------------ broadcast graphics: match detail, match board, records, event pages
@pytest.mark.parametrize("rid,sport,labels", [
    ("2002382", "Football", ["Half #1", "Half #2"]),
    ("2014273", "Basketball", ["Half #1", "Half #2"]),
    ("19001152", "Volleyball", ["Set #1", "Set #2", "Set #3", "Set #4", "Set #5"]),
    ("19020202", "Ice Hockey", ["Period #1", "Period #2", "Period #3"]),
])
def test_match_detail_has_labelled_periods_and_consistent_totals(rid, sport, labels):
    d = client.get(f"/api/matches/{rid}").json()
    assert d["sport_name"] == sport
    assert [p["label"] for p in d["periods"]] == labels
    assert d["teams"][0]["score"] == int(d["home_score"]) and d["teams"][1]["score"] == int(d["away_score"])
    main = d["stats"][0]
    if sport in ("Football", "Basketball", "Ice Hockey"):      # the team-totals row of the page agrees with the final score
        assert main["values"] == [d["teams"][0]["score"], d["teams"][1]["score"]]


def test_period_scores_follow_each_sports_convention():
    vb = client.get("/api/matches/19001152").json()
    for team in (0, 1):                                      # volleyball: set scores are per set, and the team's sets won equals the sets it scored more in
        pass
    won = [sum(1 for p in vb["periods"] if p["scores"][i] > p["scores"][1 - i]) for i in (0, 1)]
    assert won == [vb["teams"][0]["score"], vb["teams"][1]["score"]]
    bb = client.get("/api/matches/2014273").json()           # basketball: halves add up to the final score
    assert [sum(p["scores"][i] for p in bb["periods"]) for i in (0, 1)] == [bb["teams"][0]["score"], bb["teams"][1]["score"]]
    fb = client.get("/api/matches/2002382").json()           # football: Olympedia lists the running score after each half, so the last value cannot exceed the final
    assert all(fb["periods"][-1]["scores"][i] <= fb["teams"][i]["score"] for i in (0, 1)) and fb["periods"][0]["scores"][0] <= fb["periods"][-1]["scores"][0]


def test_football_goals_match_the_final_score_and_have_sides():
    d = client.get("/api/matches/2002382").json()
    assert len(d["goals"]) == d["teams"][0]["score"] + d["teams"][1]["score"]
    assert sum(1 for g in d["goals"] if g["side"] == "home") == d["teams"][0]["score"]
    assert d["substitutions"] > 0 and d["cards"]
    assert d["lineups"] and d["notes"]


def test_hockey_goals_come_from_the_running_score():
    d = client.get("/api/matches/19020202").json()
    assert [g["score"] for g in d["goals"]] == ["1-0", "1-1", "2-1"]
    assert [g["side"] for g in d["goals"]] == ["home", "away", "home"]


def test_unknown_match_is_404():
    assert client.get("/api/matches/1").status_code == 404


@pytest.mark.parametrize("games,sport", [("2022_winter", "Ice Hockey"), ("2012_summer", "Basketball"), ("2020_summer", "Volleyball"), ("2024_summer", "Football")])
def test_match_board_returns_cards_with_labelled_periods(games, sport):
    d = client.get("/api/match-board", params={"games_id": games, "sport": sport, "page_size": 5}).json()
    assert d["total"] > 20 and d["events"]
    assert all(r["periods"] and r["score_label"] for r in d["rows"])


def test_records_for_games_and_event_pages_support_the_results_view():
    recs = client.get("/api/records/for-games", params={"games_id": "2024_summer"}).json()
    assert recs and {"level", "value", "event", "athlete"} <= set(recs[0])
    pages = client.get("/api/event-pages", params={"games_id": "2024_summer", "sport": "Athletics", "event": "100 metres, Men"}).json()
    assert pages and pages[0]["event_name"] == "100 metres, Men"
    saved = client.get(f"/api/pages/{pages[0]['result_id']}").json()
    assert any(t["section"].startswith("Heat") for t in saved["tables"])


# ------------------------------------------------------------------ every round / heat table as structured data, and the results filled from it
def _db():
    from backend.database.session import engine
    return engine


def test_round_results_keep_the_heat_and_round_rows_of_the_100m():
    from sqlalchemy import text
    with _db().connect() as con:
        rows = con.execute(text("SELECT section, pos_text, mark_text, athlete_id FROM olympedia_round_results WHERE result_id='65310' AND competitor LIKE '%Saffar%' ORDER BY stage_rank DESC")).fetchall()
    assert any(r[0] == "Round One" and r[2] == "10.75" for r in rows)        # his Round One time is in the table ...
    assert any(r[0].startswith("Heat") for r in rows) and all(r[3] == "73006" for r in rows if r[3])


def test_crew_members_inherit_their_entrys_place_and_time():
    from sqlalchemy import text
    with _db().connect() as con:
        r = con.execute(text("SELECT competitor, pos_text, mark_text, team_entry FROM olympedia_round_results WHERE team_entry='Germany 1' AND event_name='Four, Men' AND mark_text='3:37.57'")).fetchall()
    assert {x[0] for x in r} >= {"Johannes Lochner", "Thorsten Margis"} and all(x[1] == "1" for x in r)


def test_event_results_are_filled_from_the_round_tables():
    from sqlalchemy import text
    with _db().connect() as con:
        n, mark, pos = con.execute(text("SELECT COUNT(*), SUM(result_value IS NOT NULL AND result_value!=''), SUM(final_position IS NOT NULL) FROM event_results")).fetchone()
        sail = con.execute(text("SELECT COUNT(*), SUM(result_value IS NOT NULL AND result_value!='') FROM event_results e JOIN sports s USING(sport_id) WHERE s.sport_name='Sailing'")).fetchone()
        bad = con.execute(text("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!='' AND result_unit='seconds' AND result_value NOT GLOB '*[0-9]*'")).fetchone()[0]
    assert mark / n > 0.70 and pos / n > 0.72
    assert sail[1] / sail[0] > 0.8      # crew events (sailing) were 0% before the round tables were used; 87% now
    assert bad == 0


# ------------------------------------------------------------------ Olympedia-style platform: event index, event page, match / bout / heat pages, medals, country at an edition
def test_edition_event_index_groups_every_event_by_sport():
    d = client.get("/api/games/2020_summer/events").json()
    assert d["total"] == 339 and "3x3 Basketball" in d["all_sports"]
    bb = client.get("/api/games/2020_summer/events", params={"sport": "3x3 Basketball", "gender": "Men"}).json()
    assert [e["result_id"] for s in bb["sports"] for e in s["events"]] == ["18000000"]
    assert client.get("/api/games/1900_summer/events").status_code == 404


def test_event_page_links_every_match_number_to_its_saved_page():
    d = client.get("/api/events/18000000").json()
    assert d["title"] == "3 × 3 Basketball, Men" and d["meta"]["Location"].startswith("Aomi")
    assert [m["noc"] for m in d["medals"]] == ["LAT", "ROC", "SRB"]
    assert [s["label"] for s in d["stages"]] == ["Final standings", "Round-Robin", "Quarter-Finals", "Semi-Finals", "Final Round"]
    routes = [x["route"] for t in d["tables"] for row in t["links"] for cell in row for x in cell if x.get("results")]
    assert len(routes) == 34 and all(r.startswith("/games/2020_summer/events/18000000/matches/") for r in routes)
    ath = d["tables"][0]["links"][1][3][0]
    assert ath["athletes"] == "145109" and ath["route"].startswith("/athletes/")


def test_match_page_has_scoreboard_and_prev_next_in_table_order():
    d = client.get("/api/subpages/18000011").json()
    assert d["type"] == "matches" and d["has_scoreboard"] and d["event"]["result_id"] == "18000000"
    assert d["nav"]["index"] == 1 and d["nav"]["count"] == 34 and d["nav"]["next"]["result_id"] == "18000012" and d["nav"]["prev"] is None
    assert client.get("/api/subpages/18000000").status_code == 404   # an event id is not a sub-page


def test_boxing_bout_routes_as_a_bout():
    d = client.get("/api/subpages/19005658").json()
    assert d["type"] == "bouts" and d["sport"] == "Boxing" and d["nav"]["count"] > 10


def test_dropdown_parts_open_their_pages():
    d = client.get("/api/events/18000080").json()
    assert d["parts"] and all(p["route"] for p in d["parts"])


def test_medals_by_country_filters_and_convention():
    d = client.get("/api/medals/countries", params={"games_id": "2024_summer", "page_size": 1}).json()
    assert (d["rows"][0]["noc"], d["rows"][0]["gold"], d["rows"][0]["silver"], d["rows"][0]["bronze"]) == ("USA", 40, 44, 42)
    assert "never merged" in d["convention"]
    urs = client.get("/api/medals/countries", params={"noc": "URS"}).json()["rows"][0]
    assert urs["noc"] == "URS" and urs["total"] == 1014
    w = client.get("/api/medals/countries", params={"games_id": "2024_summer", "gender": "Women", "medal": "Gold", "page_size": 500}).json()
    assert 0 < w["totals"]["gold"] < 329 and w["totals"]["silver"] == 0
    assert client.get("/api/medals/countries", params={"season": "winter", "format": "csv"}).headers["content-type"].startswith("text/csv")


def test_country_edition_includes_non_medal_results():
    d = client.get("/api/countries/GER/editions/2020_summer").json()
    assert d["summary"]["entries"] == 350 and d["summary"]["non_medal_entries"] == 313 and (d["summary"]["gold"], d["summary"]["silver"], d["summary"]["bronze"]) == (10, 11, 16)
    assert client.get("/api/countries/GER/editions/1900_summer").status_code == 404


def test_coverage_report_lists_every_held_edition():
    eds = client.get("/api/data-quality/coverage").json()["editions"]
    assert len(eds) == 35 and all(e["events"] and e["links"] == e["links_saved"] for e in eds if e["links"])


def test_event_page_has_olympedias_description_and_true_header_facts():
    d = client.get("/api/events/18000000").json()
    assert d["description"][0].startswith("Serbia was considered the favorite") and len(d["description"]) == 3
    assert d["meta"]["Date"] == "24 – 28 July 2021" and d["meta"]["Format"] == "Round-robin tournament, followed by single elimination."   # the header, not the last round's line
    assert d["section_meta"]["Final Round"]["Date"] == "28 July 2021 — 21:15"


def test_edition_participants_lists_every_entry_not_only_medallists():
    d = client.get("/api/games/2020_summer/participants").json()
    assert d["total"] == len(d["rows"]) > 10000 and d["athletes"] > 10000
    assert any(r["medal"] is None for r in d["rows"]) and any(r["medal"] == "Gold" for r in d["rows"])
    assert client.get("/api/games/2028_summer/participants").status_code == 404   # upcoming Games: nothing invented


def test_edition_gender_breakdown_is_consistent():
    g = client.get("/api/games/2020_summer/gender").json()
    o = g["overall"]
    assert o["men"] + o["women"] + o["unrecorded"] == o["total"] and 0 <= o["unrecorded"] < 10
    assert sum(r["total"] for r in g["by_noc"]) >= o["total"]          # an athlete is counted once per NOC entered for
    assert g["by_sport"] and g["by_event"] and all(r["men"] + r["women"] <= r["total"] for r in g["by_sport"])
    assert [p["year"] for p in g["progression"]] == sorted(p["year"] for p in g["progression"])


def test_games_can_include_upcoming_editions_flagged():
    rows = client.get("/api/games", params={"include_upcoming": 1}).json()
    up = [r for r in rows if r["upcoming"]]
    assert {r["games_id"] for r in up} == {"2028_summer", "2030_winter", "2032_summer", "2034_winter"}
    assert all(r.get("athletes") is None for r in up) and {r["host_noc"] for r in up} == {"USA", "FRA", "AUS"}
    assert len(client.get("/api/games").json()) == 35                  # default list unchanged: held Games only


def test_country_results_lists_every_entry_with_links():
    d = client.get("/api/countries/GER/results").json()
    rows = d["rows"]
    assert d["total"] == len(rows) == 5902
    assert any(r["medal"] is None for r in rows) and any(r["medal"] == "Gold" for r in rows)
    assert all(r["event_route"] is None or r["event_route"].startswith(f"/games/{r['games_id']}/events/") for r in rows)
    assert any(r["result"] for r in rows) and any(r["result"] is None for r in rows)          # missing results stay null, never estimated
    assert {r["status"] for r in rows} >= {"Ranked", "DNS"}
    assert client.get("/api/countries/ZZZ/results").status_code == 404


def test_medal_table_lists_all_nocs_with_appearances_and_search():
    d = client.get("/api/medals/countries", params={"include_all": 1, "page_size": 500}).json()
    ranked = [r for r in d["rows"] if r["total"] > 0]
    zero = [r for r in d["rows"] if r["total"] == 0]
    assert len(d["rows"]) > 200 and zero and all(r["appearances"] >= 1 for r in d["rows"])
    assert [r["rank"] for r in zero] == list(range(len(ranked) + 1, len(ranked) + 1 + len(zero)))   # no-medal NOCs continue the numbering
    assert [r["appearances"] for r in zero] == sorted((r["appearances"] for r in zero), reverse=True)  # ... most appearances first
    assert ranked[0]["noc"] == "USA" and d["rows"].index(ranked[-1]) < d["rows"].index(zero[0])   # medal holders first
    q = client.get("/api/medals/countries", params={"q": "germ", "page_size": 500}).json()["rows"]
    assert {r["noc"] for r in q} == {"GER", "GDR", "FRG", "EUA"}                                  # historical NOCs stay separate
    only = client.get("/api/medals/countries", params={"include_all": 1, "sport": "Swimming", "page_size": 500}).json()["rows"]
    assert all(r["total"] > 0 for r in only)                                                      # a sport filter keeps medal holders only


def test_sports_by_edition_matches_the_event_index():
    d = client.get("/api/sports-by-edition", params={"season": "winter"}).json()
    assert "2022_winter" in d and "2016_summer" not in d
    cur = {s["sport"]: s["events"] for s in d["2022_winter"]}
    assert cur["Curling"] == 3
    ev = client.get("/api/games/2022_winter/sports/Curling").json()
    assert ev["total"] == 3


def test_team_scoreboard_picks_the_two_team_rows_and_their_flags():
    # fencing team match: a squad-members line sits under each team, and the table has no "Number" column
    d = client.get("/api/matches/88313").json()
    assert [(t["name"], t["noc"]) for t in d["teams"]] == [("Soviet Union", "URS"), ("Italy", "ITA")]
    # table tennis team match with set scores
    d = client.get("/api/matches/46768").json()
    assert [t["noc"] for t in d["teams"]] == ["CHN", "YUG"] and d["periods"][0]["scores"] == [20, 22]


def test_individual_match_flags_come_from_the_competitors():
    d = client.get("/api/matches/130367").json()          # wrestling: NOC is stored per competitor, not on home/away
    assert (d["home_noc"], d["away_noc"]) == ("CHN", "USA")
    rows = client.get("/api/bouts", params={"games_id": "1988_summer", "sport": "Wrestling", "page_size": 5}).json()["rows"]
    assert all(r["home_noc"] for r in rows if len(r["participants"]) >= 2)


def test_medal_table_of_one_edition_loads():
    d = client.get("/api/medals/editions/2020_summer").json()
    assert d["rows"][0]["noc"] == "USA" and d["edition"]["games_id"] == "2020_summer"
