"""Parse Olympic medal tables from generic extracted wikitable structures."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


GOLD_KEYS = {"gold", "g", "golden"}
SILVER_KEYS = {"silver", "s"}
BRONZE_KEYS = {"bronze", "b"}
NOC_KEYS = {"noc", "nation", "team", "country", "olympic committee"}


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _find_col(headers: List[str], keys: set[str]) -> Optional[int]:
    for i, h in enumerate(headers):
        nh = _norm(h)
        if nh in keys or any(k in nh for k in keys):
            return i
    return None


def parse_medal_table(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best-effort parse of a medal standings table. Returns [] if structure unknown."""
    headers = [str(h) for h in table.get("headers") or []]
    if not headers:
        return []
    noc_i = _find_col(headers, NOC_KEYS)
    gold_i = _find_col(headers, GOLD_KEYS)
    silver_i = _find_col(headers, SILVER_KEYS)
    bronze_i = _find_col(headers, BRONZE_KEYS)
    if noc_i is None or gold_i is None:
        return []

    rows_out: List[Dict[str, Any]] = []
    for rank, row in enumerate(table.get("rows") or [], start=1):
        if len(row) <= max(noc_i, gold_i):
            continue
        def _int(idx: Optional[int]) -> int:
            if idx is None or idx >= len(row):
                return 0
            m = re.search(r"\d+", str(row[idx]))
            return int(m.group()) if m else 0

        gold = _int(gold_i)
        silver = _int(silver_i)
        bronze = _int(bronze_i)
        rows_out.append(
            {
                "official_rank": rank,
                "country_name": str(row[noc_i]).strip(),
                "gold": gold,
                "silver": silver,
                "bronze": bronze,
                "total": gold + silver + bronze,
                "verification_status": "collected",
                "source": "wikipedia_table",
            }
        )
    return rows_out
