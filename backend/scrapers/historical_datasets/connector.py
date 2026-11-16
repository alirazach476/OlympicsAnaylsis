"""Historical dataset importers (Phase 2).

Sources:
- https://github.com/ismayc/olympic-moderndive-data
- https://dataful.in/collections/701/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)

KNOWN_DATASETS = [
    {
        "name": "olympic-moderndive-data",
        "url": "https://raw.githubusercontent.com/ismayc/olympic-moderndive-data/master/data/olympics.csv",
        "format": "csv",
        "authority": "curated_third_party",
        "notes": "Import to raw/; reconcile — do not treat as sole authority.",
    },
]


class HistoricalDatasetsConnector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.raw_dir = self.settings.project_root / "data" / "raw" / "historical_datasets"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.wiki_user_agent})

    def list_known(self) -> list:
        return list(KNOWN_DATASETS)

    def download(self, name: str) -> Optional[Path]:
        meta = next((d for d in KNOWN_DATASETS if d["name"] == name), None)
        if not meta:
            raise KeyError(name)
        url = meta["url"]
        logger.info("Downloading historical dataset %s", url)
        resp = self.session.get(url, timeout=120)
        if resp.status_code != 200:
            logger.warning("Dataset download failed %s -> %s", url, resp.status_code)
            return None
        out = self.raw_dir / f"{name}.{meta['format']}"
        out.write_bytes(resp.content)
        # provenance sidecar
        (self.raw_dir / f"{name}.provenance.json").write_text(
            __import__("json").dumps(
                {**meta, "downloaded": True, "http_status": resp.status_code},
                indent=2,
            ),
            encoding="utf-8",
        )
        return out
