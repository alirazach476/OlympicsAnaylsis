"""Official Olympics.com connector scaffold (Phase 2).

Preferred authority for official results and medal standings where available.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)
BASE_URL = "https://www.olympics.com"


class OlympicsOfficialConnector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.raw_dir = self.settings.project_root / "data" / "raw" / "olympics_official"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.wiki_user_agent})

    def fetch_url(self, url: str) -> Optional[Path]:
        logger.info("Fetching official Olympics URL %s", url)
        resp = self.session.get(url, timeout=60)
        if resp.status_code != 200:
            logger.warning("Official fetch failed %s -> %s", url, resp.status_code)
            return None
        name = url.rstrip("/").split("/")[-1] or "page"
        out = self.raw_dir / f"{name}.html"
        out.write_text(resp.text, encoding="utf-8")
        return out

    def coverage_notes(self) -> dict:
        return {
            "source": "olympics_official",
            "base_url": BASE_URL,
            "status": "connector_scaffolded",
            "phase": 2,
            "authority": "preferred_for_official_results_and_medal_tables",
            "notes": (
                "Site is dynamic; Playwright may be required for some pages. "
                "Never hardcode medal totals."
            ),
        }
