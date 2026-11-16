"""Olympedia edition IDs for Summer/Winter Games 1960–2026.

Source index: https://www.olympedia.org/editions/results
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# games_id -> olympedia edition_id
OLYMPEDIA_EDITION_IDS: Dict[str, int] = {
    # Summer
    "1960_summer": 15,
    "1964_summer": 16,
    "1968_summer": 17,
    "1972_summer": 18,
    "1976_summer": 19,
    "1980_summer": 20,
    "1984_summer": 21,
    "1988_summer": 22,
    "1992_summer": 23,
    "1996_summer": 24,
    "2000_summer": 25,
    "2004_summer": 26,
    "2008_summer": 53,
    "2012_summer": 54,
    "2016_summer": 59,
    "2020_summer": 61,
    "2024_summer": 63,
    # Winter
    "1960_winter": 36,
    "1964_winter": 37,
    "1968_winter": 38,
    "1972_winter": 39,
    "1976_winter": 40,
    "1980_winter": 41,
    "1984_winter": 42,
    "1988_winter": 43,
    "1992_winter": 44,
    "1994_winter": 45,
    "1998_winter": 46,
    "2002_winter": 47,
    "2006_winter": 49,
    "2010_winter": 57,
    "2014_winter": 58,
    "2018_winter": 60,
    "2022_winter": 62,
    "2026_winter": 72,
}


def edition_result_url(edition_id: int) -> str:
    return f"https://www.olympedia.org/editions/{edition_id}/result"


def result_url(result_id: int | str) -> str:
    return f"https://www.olympedia.org/results/{result_id}"


def all_scoped_editions() -> List[Tuple[str, int]]:
    return sorted(OLYMPEDIA_EDITION_IDS.items(), key=lambda kv: (kv[0].split("_")[1], kv[0]))
