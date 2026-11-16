from backend.scrapers.wikipedia.relevance import score_relevance
from backend.scrapers.wikipedia.urls import normalize_wikipedia_url, title_to_url


def test_normalize_strips_fragment_and_query():
    url = "https://en.wikipedia.org/wiki/1960_Summer_Olympics#Medal_table?oldid=1"
    assert (
        normalize_wikipedia_url(url)
        == "https://en.wikipedia.org/wiki/1960_Summer_Olympics"
    )


def test_normalize_rejects_file_and_category():
    assert normalize_wikipedia_url("https://en.wikipedia.org/wiki/File:Logo.svg") is None
    assert normalize_wikipedia_url("/wiki/Category:Olympics") is None


def test_title_to_url():
    assert "1960_Summer_Olympics" in title_to_url("1960 Summer Olympics")


def test_relevance_seed_page_high():
    r = score_relevance(
        title="1960 Summer Olympics",
        games_year=1960,
        season="summer",
        categories=["Category:1960 Summer Olympics"],
        depth=0,
    )
    assert r.score >= 0.7
    assert not r.excluded
    assert r.page_category == "edition"


def test_relevance_sport_page():
    r = score_relevance(
        title="Athletics at the 1960 Summer Olympics",
        games_year=1960,
        season="summer",
        parent_title="1960 Summer Olympics",
        depth=1,
    )
    assert r.score >= 0.45
    assert r.page_category == "sport_at_games"


def test_relevance_unrelated_low():
    r = score_relevance(
        title="List of songs recorded by Madonna",
        games_year=1960,
        season="summer",
        depth=2,
    )
    assert r.excluded or r.score < 0.2
