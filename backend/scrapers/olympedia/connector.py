"""Olympedia source connector (Phase 2).

https://www.olympedia.org/

This connector downloads and stores raw HTML/structured pages with provenance.
It does not invent athlete or result records. Full parsing expands in Phase 2.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)
BASE_URL = "https://www.olympedia.org"


class OlympediaConnector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.raw_dir = self.settings.project_root / "data" / "raw" / "olympedia"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.wiki_user_agent})

    def fetch_path(self, path: str) -> Optional[Path]:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        logger.info("Fetching Olympedia URL %s", url)
        resp = self.session.get(url, timeout=60)
        if resp.status_code != 200:
            logger.warning("Olympedia fetch failed %s -> %s", url, resp.status_code)
            return None
        safe = path.strip("/").replace("/", "_") or "index"
        out = self.raw_dir / f"{safe}.html"
        out.write_text(resp.text, encoding="utf-8")
        return out

    def coverage_notes(self) -> dict:
        return {
            "source": "olympedia",
            "base_url": BASE_URL,
            "status": "results_scraper_active",
            "phase": 2,
            "authority": "high_for_athlete_biographies_and_results",
            "index": f"{BASE_URL}/editions/results",
            "notes": (
                "Edition result indexes + event pages + nested Match fixtures "
                "via OlympediaResultsScraper; raw HTML under data/raw/olympedia."
            ),
        }
