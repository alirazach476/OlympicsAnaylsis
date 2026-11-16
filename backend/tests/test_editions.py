from backend.collectors.editions import SUMMER_EDITIONS, WINTER_EDITIONS, all_editions


def test_summer_range_and_no_2026_summer():
    years = [e.year for e in SUMMER_EDITIONS]
    assert min(years) == 1960
    assert max(years) == 2024
    assert 2026 not in years
    assert all(e.season == "summer" for e in SUMMER_EDITIONS)


def test_winter_includes_2026():
    years = [e.year for e in WINTER_EDITIONS]
    assert min(years) == 1960
    assert max(years) == 2026
    assert any(e.games_id == "2026_winter" for e in WINTER_EDITIONS)


def test_tokyo_2020_actual_dates_in_2021():
    tokyo = next(e for e in SUMMER_EDITIONS if e.games_id == "2020_summer")
    assert tokyo.year == 2020
    assert tokyo.actual_event_start_date.year == 2021
    assert tokyo.actual_event_end_date.year == 2021
    assert "2020" in tokyo.wikipedia_title


def test_unique_games_ids():
    ids = [e.games_id for e in all_editions()]
    assert len(ids) == len(set(ids))
    assert len(ids) == 17 + 18  # 17 summer + 18 winter
