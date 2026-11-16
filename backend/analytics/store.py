"""Shared helpers: warehouse connection + analytics_results store (JSON payloads served by the API)."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "olympics_warehouse.db"


def connect(readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout=300000")
    con.executescript(
        """CREATE TABLE IF NOT EXISTS analytics_results(
             module TEXT, key TEXT, title TEXT, question TEXT, payload_json TEXT, generated_at TEXT, PRIMARY KEY(module, key));
           CREATE TABLE IF NOT EXISTS analytics_hypothesis_tests(
             test_id TEXT PRIMARY KEY, family TEXT, research_question TEXT, null_hypothesis TEXT, alternative_hypothesis TEXT, method TEXT, why_this_test TEXT,
             assumptions_json TEXT, n INTEGER, statistic REAL, p_value REAL, p_adjusted_holm REAL, ci_low REAL, ci_high REAL, ci_level REAL,
             effect_size_name TEXT, effect_size REAL, interpretation TEXT, caveats TEXT, generated_at TEXT);"""
    )
    return con


def _clean(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return None if np.isnan(v) or np.isinf(v) else v
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return [_clean(x) for x in o.tolist()]
    if isinstance(o, pd.DataFrame):
        return [_clean(r) for r in o.to_dict("records")]
    if isinstance(o, pd.Series):
        return _clean(o.to_dict())
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_clean(x) for x in o]
    if isinstance(o, float):
        return None if np.isnan(o) or np.isinf(o) else o
    if o is pd.NaT:
        return None
    return o


def save(con: sqlite3.Connection, module: str, key: str, title: str, payload, question: str = "") -> None:
    con.execute(
        "INSERT OR REPLACE INTO analytics_results VALUES (?,?,?,?,?,?)",
        (module, key, title, question, json.dumps(_clean(payload), ensure_ascii=False), dt.datetime.now(dt.timezone.utc).isoformat()),
    )
    con.commit()


def load(con: sqlite3.Connection, module: str, key: str | None = None):
    if key:
        r = con.execute("SELECT payload_json, title, question, generated_at FROM analytics_results WHERE module=? AND key=?", (module, key)).fetchone()
        return None if not r else {"module": module, "key": key, "title": r[1], "question": r[2], "generated_at": r[3], "data": json.loads(r[0])}
    return [{"module": module, "key": k, "title": t, "question": q, "generated_at": g} for k, t, q, g in
            con.execute("SELECT key, title, question, generated_at FROM analytics_results WHERE module=? ORDER BY key", (module,))]
