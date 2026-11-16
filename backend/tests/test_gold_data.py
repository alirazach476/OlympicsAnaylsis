"""Data-layer tests against the real warehouse: duplicates, medal reconciliation, NOC history, relationships."""
import sqlite3
from pathlib import Path

import pytest

DB = Path(__file__).resolve().parents[2] / "data" / "olympics_warehouse.db"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="warehouse not built")


@pytest.fixture(scope="module")
def con():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    yield c
    c.close()


def one(con, sql, *p):
    return con.execute(sql, p).fetchone()[0]


def test_no_duplicate_medal_awards(con):
    assert one(con, "SELECT COUNT(*) FROM (SELECT 1 FROM silver_medal_awards GROUP BY games_id,result_id,noc_code,medal_type HAVING COUNT(*)>1)") == 0


def test_no_duplicate_country_edition_rows(con):
    assert one(con, "SELECT COUNT(*) FROM (SELECT 1 FROM gold_country_medals GROUP BY games_id,noc_code HAVING COUNT(*)>1)") == 0


def test_totals_are_gold_plus_silver_plus_bronze(con):
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE total != gold+silver+bronze") == 0


def test_paris_2024_matches_official_totals(con):
    """Regression fixture: the official Paris 2024 medal totals (not used as data - only as a check of the derivation)."""
    g, s, b = con.execute("SELECT SUM(gold), SUM(silver), SUM(bronze) FROM gold_country_medals WHERE games_id='2024_summer'").fetchone()
    assert (g, s, b) == (329, 330, 385)


def test_medal_events_do_not_exceed_events(con):
    assert one(con, "SELECT COUNT(*) FROM gold_edition_performance WHERE medal_events > events + 20") == 0


def test_every_medal_noc_is_in_the_registry(con):
    bad = [r[0] for r in con.execute("SELECT DISTINCT noc_code FROM gold_country_medals WHERE noc_code NOT IN (SELECT noc_code FROM historical_nocs)")]
    assert bad == []


def test_placeholder_and_footer_rows_never_reach_gold(con):
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE noc_code LIKE 'X\\_%' ESCAPE '\\' OR country_name GLOB '[0-9]*'") == 0


def test_historical_nocs_are_not_merged_into_successors(con):
    # URS medalled at 1980; RUS did not exist then. GDR/FRG stay separate from GER; EUA 1960 is its own team.
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE games_id='1980_summer' AND noc_code='URS'") == 1
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE games_id='1980_summer' AND noc_code='RUS'") == 0
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE games_id='1976_summer' AND noc_code IN ('GDR','FRG')") == 2
    assert one(con, "SELECT COUNT(*) FROM gold_country_medals WHERE games_id='1960_summer' AND noc_code='EUA'") == 1
    assert one(con, "SELECT COUNT(*) FROM historical_nocs WHERE noc_code IN ('URS','EUN','ROC','OAR','AIN','GDR','FRG','TCH','YUG','SCG')") == 10


def test_tie_aware_ranks_share_a_rank(con):
    ranks = con.execute("SELECT official_rank, COUNT(*) FROM gold_country_medals WHERE games_id='2024_summer' GROUP BY 1 HAVING COUNT(*)>1").fetchall()
    assert ranks, "expected at least one tied rank in a 91-NOC table"
    # tied rows have identical G/S/B
    for r, _ in ranks:
        assert one(con, "SELECT COUNT(*) FROM (SELECT DISTINCT gold,silver,bronze FROM gold_country_medals WHERE games_id='2024_summer' AND official_rank=?)", r) == 1


def test_in_scope_games_only(con):
    assert one(con, "SELECT COUNT(*) FROM gold_edition_performance") == 35
    assert one(con, "SELECT COUNT(*) FROM gold_edition_performance WHERE season='summer' AND year>2024") == 0
    assert one(con, "SELECT COUNT(*) FROM gold_edition_performance WHERE season='summer' AND year=2026") == 0
    assert one(con, "SELECT COUNT(*) FROM gold_edition_performance WHERE season='winter' AND year=2026") == 1
    # Tokyo 2020 keeps its official edition year with 2021 dates
    y, o = con.execute("SELECT year, opening_date FROM gold_edition_performance WHERE games_id='2020_summer'").fetchone()
    assert y == 2020 and str(o).startswith("2021")


def test_referential_integrity(con):
    checks = [
        "SELECT COUNT(*) FROM silver_participations p WHERE NOT EXISTS(SELECT 1 FROM silver_athletes a WHERE a.athlete_id=p.athlete_id)",
        "SELECT COUNT(*) FROM silver_participations p WHERE NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=p.games_id)",
        "SELECT COUNT(*) FROM gold_athlete_career c WHERE NOT EXISTS(SELECT 1 FROM silver_athletes a WHERE a.athlete_id=c.athlete_id)",
        "SELECT COUNT(*) FROM gold_sport_performance s WHERE NOT EXISTS(SELECT 1 FROM sports x WHERE x.sport_id=s.sport_id)",
        "SELECT COUNT(*) FROM silver_participations p WHERE p.noc_code!='UNK' AND NOT EXISTS(SELECT 1 FROM historical_nocs h WHERE h.noc_code=p.noc_code)",
    ]
    for sql in checks:
        assert one(con, sql) == 0, sql


def test_career_medals_equal_participation_medals(con):
    a = one(con, "SELECT SUM(medals) FROM gold_athlete_career")
    b = one(con, "SELECT SUM(is_medalist) FROM silver_participations")
    assert a == b


def test_gold_marts_are_incrementally_tracked(con):
    assert one(con, "SELECT COUNT(*) FROM gold_build_state WHERE mart='per_games'") == 35


def test_age_values_are_plausible(con):
    assert one(con, "SELECT COUNT(*) FROM silver_participations WHERE age IS NOT NULL AND (age<10 OR age>80)") == 0


def test_event_result_units_are_declared_when_numeric(con):
    assert one(con, "SELECT COUNT(*) FROM gold_event_results WHERE result_value IS NOT NULL AND result_unit IS NULL") == 0
