"""Master registry of Summer (1960–2024) and Winter (1960–2026) Olympic editions.

Tokyo 2020 retains official edition year 2020 with actual 2021 event dates.
No Summer 2026 edition is defined.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class OlympicEdition:
    games_id: str
    year: int
    season: str  # summer | winter
    official_edition_name: str
    edition_number: Optional[int]
    host_city: str
    host_country: str
    opening_date: Optional[date]
    closing_date: Optional[date]
    actual_event_start_date: Optional[date]
    actual_event_end_date: Optional[date]
    wikipedia_title: str
    olympedia_url: Optional[str] = None
    official_website: Optional[str] = None
    source: str = "seed_registry"
    verification_status: str = "partially_verified"

    @property
    def wikipedia_url(self) -> str:
        slug = self.wikipedia_title.replace(" ", "_")
        return f"https://en.wikipedia.org/wiki/{slug}"

    def to_dict(self) -> Dict:
        d = asdict(self)
        for key in (
            "opening_date",
            "closing_date",
            "actual_event_start_date",
            "actual_event_end_date",
        ):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        d["wikipedia_url"] = self.wikipedia_url
        return d


def _d(y: int, m: int, day: int) -> date:
    return date(y, m, day)


# Host / date facts are seed metadata for crawl association.
# Detailed counts (athletes, events, etc.) are filled by collectors — not invented here.
SUMMER_EDITIONS: List[OlympicEdition] = [
    OlympicEdition("1960_summer", 1960, "summer", "Games of the XVII Olympiad", 17, "Rome", "Italy", _d(1960, 8, 25), _d(1960, 9, 11), _d(1960, 8, 25), _d(1960, 9, 11), "1960 Summer Olympics"),
    OlympicEdition("1964_summer", 1964, "summer", "Games of the XVIII Olympiad", 18, "Tokyo", "Japan", _d(1964, 10, 10), _d(1964, 10, 24), _d(1964, 10, 10), _d(1964, 10, 24), "1964 Summer Olympics"),
    OlympicEdition("1968_summer", 1968, "summer", "Games of the XIX Olympiad", 19, "Mexico City", "Mexico", _d(1968, 10, 12), _d(1968, 10, 27), _d(1968, 10, 12), _d(1968, 10, 27), "1968 Summer Olympics"),
    OlympicEdition("1972_summer", 1972, "summer", "Games of the XX Olympiad", 20, "Munich", "West Germany", _d(1972, 8, 26), _d(1972, 9, 11), _d(1972, 8, 26), _d(1972, 9, 11), "1972 Summer Olympics"),
    OlympicEdition("1976_summer", 1976, "summer", "Games of the XXI Olympiad", 21, "Montreal", "Canada", _d(1976, 7, 17), _d(1976, 8, 1), _d(1976, 7, 17), _d(1976, 8, 1), "1976 Summer Olympics"),
    OlympicEdition("1980_summer", 1980, "summer", "Games of the XXII Olympiad", 22, "Moscow", "Soviet Union", _d(1980, 7, 19), _d(1980, 8, 3), _d(1980, 7, 19), _d(1980, 8, 3), "1980 Summer Olympics"),
    OlympicEdition("1984_summer", 1984, "summer", "Games of the XXIII Olympiad", 23, "Los Angeles", "United States", _d(1984, 7, 28), _d(1984, 8, 12), _d(1984, 7, 28), _d(1984, 8, 12), "1984 Summer Olympics"),
    OlympicEdition("1988_summer", 1988, "summer", "Games of the XXIV Olympiad", 24, "Seoul", "South Korea", _d(1988, 9, 17), _d(1988, 10, 2), _d(1988, 9, 17), _d(1988, 10, 2), "1988 Summer Olympics"),
    OlympicEdition("1992_summer", 1992, "summer", "Games of the XXV Olympiad", 25, "Barcelona", "Spain", _d(1992, 7, 25), _d(1992, 8, 9), _d(1992, 7, 25), _d(1992, 8, 9), "1992 Summer Olympics"),
    OlympicEdition("1996_summer", 1996, "summer", "Games of the XXVI Olympiad", 26, "Atlanta", "United States", _d(1996, 7, 19), _d(1996, 8, 4), _d(1996, 7, 19), _d(1996, 8, 4), "1996 Summer Olympics"),
    OlympicEdition("2000_summer", 2000, "summer", "Games of the XXVII Olympiad", 27, "Sydney", "Australia", _d(2000, 9, 15), _d(2000, 10, 1), _d(2000, 9, 15), _d(2000, 10, 1), "2000 Summer Olympics"),
    OlympicEdition("2004_summer", 2004, "summer", "Games of the XXVIII Olympiad", 28, "Athens", "Greece", _d(2004, 8, 13), _d(2004, 8, 29), _d(2004, 8, 13), _d(2004, 8, 29), "2004 Summer Olympics"),
    OlympicEdition("2008_summer", 2008, "summer", "Games of the XXIX Olympiad", 29, "Beijing", "China", _d(2008, 8, 8), _d(2008, 8, 24), _d(2008, 8, 8), _d(2008, 8, 24), "2008 Summer Olympics"),
    OlympicEdition("2012_summer", 2012, "summer", "Games of the XXX Olympiad", 30, "London", "United Kingdom", _d(2012, 7, 27), _d(2012, 8, 12), _d(2012, 7, 27), _d(2012, 8, 12), "2012 Summer Olympics"),
    OlympicEdition("2016_summer", 2016, "summer", "Games of the XXXI Olympiad", 31, "Rio de Janeiro", "Brazil", _d(2016, 8, 5), _d(2016, 8, 21), _d(2016, 8, 5), _d(2016, 8, 21), "2016 Summer Olympics"),
    # Official edition year 2020; postponed to 2021.
    OlympicEdition("2020_summer", 2020, "summer", "Games of the XXXII Olympiad", 32, "Tokyo", "Japan", _d(2021, 7, 23), _d(2021, 8, 8), _d(2021, 7, 23), _d(2021, 8, 8), "2020 Summer Olympics"),
    OlympicEdition("2024_summer", 2024, "summer", "Games of the XXXIII Olympiad", 33, "Paris", "France", _d(2024, 7, 26), _d(2024, 8, 11), _d(2024, 7, 26), _d(2024, 8, 11), "2024 Summer Olympics"),
]

WINTER_EDITIONS: List[OlympicEdition] = [
    OlympicEdition("1960_winter", 1960, "winter", "VIII Olympic Winter Games", 8, "Squaw Valley", "United States", _d(1960, 2, 18), _d(1960, 2, 28), _d(1960, 2, 18), _d(1960, 2, 28), "1960 Winter Olympics"),
    OlympicEdition("1964_winter", 1964, "winter", "IX Olympic Winter Games", 9, "Innsbruck", "Austria", _d(1964, 1, 29), _d(1964, 2, 9), _d(1964, 1, 29), _d(1964, 2, 9), "1964 Winter Olympics"),
    OlympicEdition("1968_winter", 1968, "winter", "X Olympic Winter Games", 10, "Grenoble", "France", _d(1968, 2, 6), _d(1968, 2, 18), _d(1968, 2, 6), _d(1968, 2, 18), "1968 Winter Olympics"),
    OlympicEdition("1972_winter", 1972, "winter", "XI Olympic Winter Games", 11, "Sapporo", "Japan", _d(1972, 2, 3), _d(1972, 2, 13), _d(1972, 2, 3), _d(1972, 2, 13), "1972 Winter Olympics"),
    OlympicEdition("1976_winter", 1976, "winter", "XII Olympic Winter Games", 12, "Innsbruck", "Austria", _d(1976, 2, 4), _d(1976, 2, 15), _d(1976, 2, 4), _d(1976, 2, 15), "1976 Winter Olympics"),
    OlympicEdition("1980_winter", 1980, "winter", "XIII Olympic Winter Games", 13, "Lake Placid", "United States", _d(1980, 2, 13), _d(1980, 2, 24), _d(1980, 2, 13), _d(1980, 2, 24), "1980 Winter Olympics"),
    OlympicEdition("1984_winter", 1984, "winter", "XIV Olympic Winter Games", 14, "Sarajevo", "Yugoslavia", _d(1984, 2, 8), _d(1984, 2, 19), _d(1984, 2, 8), _d(1984, 2, 19), "1984 Winter Olympics"),
    OlympicEdition("1988_winter", 1988, "winter", "XV Olympic Winter Games", 15, "Calgary", "Canada", _d(1988, 2, 13), _d(1988, 2, 28), _d(1988, 2, 13), _d(1988, 2, 28), "1988 Winter Olympics"),
    OlympicEdition("1992_winter", 1992, "winter", "XVI Olympic Winter Games", 16, "Albertville", "France", _d(1992, 2, 8), _d(1992, 2, 23), _d(1992, 2, 8), _d(1992, 2, 23), "1992 Winter Olympics"),
    OlympicEdition("1994_winter", 1994, "winter", "XVII Olympic Winter Games", 17, "Lillehammer", "Norway", _d(1994, 2, 12), _d(1994, 2, 27), _d(1994, 2, 12), _d(1994, 2, 27), "1994 Winter Olympics"),
    OlympicEdition("1998_winter", 1998, "winter", "XVIII Olympic Winter Games", 18, "Nagano", "Japan", _d(1998, 2, 7), _d(1998, 2, 22), _d(1998, 2, 7), _d(1998, 2, 22), "1998 Winter Olympics"),
    OlympicEdition("2002_winter", 2002, "winter", "XIX Olympic Winter Games", 19, "Salt Lake City", "United States", _d(2002, 2, 8), _d(2002, 2, 24), _d(2002, 2, 8), _d(2002, 2, 24), "2002 Winter Olympics"),
    OlympicEdition("2006_winter", 2006, "winter", "XX Olympic Winter Games", 20, "Turin", "Italy", _d(2006, 2, 10), _d(2006, 2, 26), _d(2006, 2, 10), _d(2006, 2, 26), "2006 Winter Olympics"),
    OlympicEdition("2010_winter", 2010, "winter", "XXI Olympic Winter Games", 21, "Vancouver", "Canada", _d(2010, 2, 12), _d(2010, 2, 28), _d(2010, 2, 12), _d(2010, 2, 28), "2010 Winter Olympics"),
    OlympicEdition("2014_winter", 2014, "winter", "XXII Olympic Winter Games", 22, "Sochi", "Russia", _d(2014, 2, 7), _d(2014, 2, 23), _d(2014, 2, 7), _d(2014, 2, 23), "2014 Winter Olympics"),
    OlympicEdition("2018_winter", 2018, "winter", "XXIII Olympic Winter Games", 23, "Pyeongchang", "South Korea", _d(2018, 2, 9), _d(2018, 2, 25), _d(2018, 2, 9), _d(2018, 2, 25), "2018 Winter Olympics"),
    OlympicEdition("2022_winter", 2022, "winter", "XXIV Olympic Winter Games", 24, "Beijing", "China", _d(2022, 2, 4), _d(2022, 2, 20), _d(2022, 2, 4), _d(2022, 2, 20), "2022 Winter Olympics"),
    OlympicEdition("2026_winter", 2026, "winter", "XXV Olympic Winter Games", 25, "Milano Cortina", "Italy", _d(2026, 2, 6), _d(2026, 2, 22), _d(2026, 2, 6), _d(2026, 2, 22), "2026 Winter Olympics"),
]


def all_editions() -> List[OlympicEdition]:
    return list(SUMMER_EDITIONS) + list(WINTER_EDITIONS)


def editions_by_season(season: str) -> List[OlympicEdition]:
    season = season.lower()
    return [e for e in all_editions() if e.season == season]


def get_edition(games_id: str) -> OlympicEdition:
    for e in all_editions():
        if e.games_id == games_id:
            return e
    raise KeyError(f"Unknown games_id: {games_id}")


def seed_titles() -> Iterable[str]:
    for e in all_editions():
        yield e.wikipedia_title
