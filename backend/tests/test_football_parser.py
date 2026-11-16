"""Regression: a kickoff time ('17:00') must never be read as a score."""
from backend.scrapers.wikipedia.football import SCORE_CELL, split_score_line


def test_kickoff_time_is_not_a_score():
    left, hg, ag, away = split_score_line("26 August 1960 17:00 Bulgaria 3–0 Turkey Report Stadio Flaminio")
    assert (hg, ag) == ("3", "0") and left.endswith("Bulgaria") and away == "Turkey"


def test_various_dashes_and_evening_kickoffs():
    assert split_score_line("24 July 2024 21:00 France 3-0 United States")[1:3] == ("3", "0")
    assert split_score_line("8 August 2024 18:30 Spain 5—3 France Report")[1:3] == ("5", "3")


def test_line_without_a_score_is_rejected():
    assert split_score_line("26 August 1960 17:00 Bulgaria v Turkey") is None


def test_score_cell_does_not_accept_a_clock_time():
    assert SCORE_CELL.match("17:00") is None
    assert SCORE_CELL.match("2–1").groups() == ("2", "1")
