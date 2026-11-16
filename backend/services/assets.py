"""Olympic asset downloader — verifies source-page association before download."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)


class AssetDownloader:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(self.settings.assets_root)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.wiki_user_agent})

    def target_dir(self, asset_type: str, season: Optional[str] = None) -> Path:
        mapping = {
            "olympic_logo": self.root / "olympic_logos" / (season or "summer"),
            "country_flag": self.root / "country_flags",
            "sport_logo": self.root / "sport_logos",
            "athlete_image": self.root / "athlete_images",
            "venue_image": self.root / "venue_images",
            "mascot": self.root / "mascots",
            "poster": self.root / "posters",
        }
        path = mapping.get(asset_type, self.root / "misc")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def filename_matches_edition(self, title: str, year: int, season: str) -> bool:
        t = title.lower()
        return str(year) in t and ("olympic" in t or season.lower() in t)

    def download(
        self,
        *,
        url: str,
        asset_type: str,
        games_id: str,
        license_name: Optional[str],
        attribution: Optional[str],
        source_page: Optional[str],
        season: Optional[str] = None,
        verified_for_edition: bool = False,
    ) -> Optional[Path]:
        if not self.settings.download_images:
            logger.info("DOWNLOAD_IMAGES=false — skipping download of %s", url)
            return None
        if not verified_for_edition:
            logger.warning(
                "Refusing download without edition verification: %s (source=%s)",
                url,
                source_page,
            )
            return None

        resp = self.session.get(url, timeout=60)
        if resp.status_code != 200:
            logger.warning("Asset download failed %s -> %s", url, resp.status_code)
            return None

        name = Path(urlparse(url).path).name or "asset.bin"
        name = re.sub(r"[^\w.\-]+", "_", name)
        dest = self.target_dir(asset_type, season) / f"{games_id}__{name}"
        dest.write_bytes(resp.content)
        meta = dest.with_suffix(dest.suffix + ".meta.txt")
        meta.write_text(
            f"url={url}\nlicense={license_name}\nattribution={attribution}\n"
            f"source_page={source_page}\ngames_id={games_id}\n",
            encoding="utf-8",
        )
        return dest
