from backend.scrapers.olympedia.connector import OlympediaConnector
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS, all_scoped_editions
from backend.scrapers.olympedia.results import OlympediaResultsScraper

__all__ = [
    "OlympediaConnector",
    "OlympediaResultsScraper",
    "OLYMPEDIA_EDITION_IDS",
    "all_scoped_editions",
]
