"""Vercel serverless entry point for the Olympics API (free tier, no always-on server).

Cold start:
  1. download the gzipped slim-warehouse shards (built by scripts/build_slim_db.py) from the public
     Hugging Face dataset in parallel;
  2. deserialize them into one in-memory sqlite3 connection: the first shard as ``main``, the others attached
     as ``m0``, ``m1``, ... (SQLite resolves unqualified table names across attached schemas);
  3. hand that connection to backend.memdb and import backend.api.main, whose engine then uses it.
Warm invocations reuse the loaded databases. Set OLY_LOCAL_SHARDS=<dir> to load the .gz files from disk instead
(used to test this exact boot path locally).

Environment (all optional): OLY_HF_REPO, OLY_HF_PREFIX, HF_TOKEN (only if the dataset is made private).
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # bundle root holds the backend/ package

REPO = os.environ.get("OLY_HF_REPO", "alirazach/olympics-slim")  # public dataset: no token needed
PREFIX = os.environ.get("OLY_HF_PREFIX", "slim")


def _fetch(name: str) -> bytes:
    local = os.environ.get("OLY_LOCAL_SHARDS")
    if local:
        return (Path(local) / name).read_bytes()
    import requests

    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{PREFIX}/{name}"
    headers = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"} if os.environ.get("HF_TOKEN") else {}
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=120)
            r.raise_for_status()
            return r.content
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("unreachable")


def boot() -> dict:
    t0 = time.time()
    manifest = json.loads(_fetch("manifest.json"))
    names = [manifest["disk"], *manifest["mem"]]
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        blobs = dict(zip(names, ex.map(_fetch, names)))
    # Everything lives in RAM: Vercel's small /tmp is already used by the runtime's dependency cache.
    con = sqlite3.connect(":memory:", check_same_thread=False)
    for i, name in enumerate(names):
        schema = "main" if i == 0 else f"m{i - 1}"
        if schema != "main":
            con.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
        data = gzip.decompress(blobs.pop(name))
        con.deserialize(data, name=schema)
        del data
    con.execute("PRAGMA query_only = ON")
    from backend import memdb

    memdb.CONN = con
    os.environ.setdefault("CORS_ORIGINS", "*")
    os.environ.setdefault("OLY_QCACHE_MAX", "16")
    return {"version": manifest.get("version"), "boot_seconds": round(time.time() - t0, 1)}


BOOT = boot()

from backend.api.main import app as api  # noqa: E402  (must import after the databases are in place)


@api.get("/api/_boot", include_in_schema=False)
def _boot_info() -> dict:
    return BOOT


async def app(scope, receive, send):
    """vercel.json rewrites every request to /api/index?__path=<original path>; restore the path for FastAPI."""
    if scope["type"] == "http":
        qs = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        orig = next((v for k, v in qs if k == "__path"), None)
        if orig is not None:
            rest = urlencode([(k, v) for k, v in qs if k != "__path"]).encode("latin-1")
            scope = {**scope, "path": orig, "raw_path": orig.encode("utf-8"), "query_string": rest}
    await api(scope, receive, send)
