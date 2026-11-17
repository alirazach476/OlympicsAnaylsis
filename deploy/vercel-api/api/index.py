"""Vercel serverless entry point for the Olympics API (free tier, no always-on server).

Cold start:
  1. download the compressed slim-warehouse shards (built by scripts/build_slim_db.py) from the public
     Hugging Face dataset in parallel threads, unpacking each as it arrives, while the app code is imported;
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


def _load_shard(name: str) -> bytes:
    """Download one shard and unpack it (zstd, or gzip for older manifests). Runs in a worker thread: both the
    network wait and the decompression release the GIL, so this overlaps with importing the application."""
    blob = _fetch(name)
    if name.endswith(".zst"):
        import zstandard

        return zstandard.ZstdDecompressor().decompress(blob)
    return gzip.decompress(blob)


# Environment for the application modules (read when they are imported).
os.environ["OLY_SERVERLESS"] = "1"   # engine connects to the in-memory warehouse, resolved lazily
os.environ["OLY_LAZY_VIZ"] = "1"     # chart stack (pandas/numpy/scipy) is imported on the first /api/viz request
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("OLY_QCACHE_MAX", "16")

_T0 = time.time()
_PHASE: dict = {}
_MANIFEST = json.loads(_fetch("manifest.json"))
_NAMES = [_MANIFEST["disk"], *_MANIFEST["mem"]]
_POOL = ThreadPoolExecutor(max_workers=len(_NAMES))
_FUTURES = {n: _POOL.submit(_load_shard, n) for n in _NAMES}   # start downloading right away ...

_PHASE["manifest_s"] = round(time.time() - _T0, 2)
from backend.api.main import app as api  # noqa: E402  ... while the application code is imported
_PHASE["import_s"] = round(time.time() - _T0, 2)


def boot() -> dict:
    # Everything lives in RAM: Vercel's small /tmp is already used by the runtime's dependency cache.
    con = sqlite3.connect(":memory:", check_same_thread=False)
    for i, name in enumerate(_NAMES):
        schema = "main" if i == 0 else f"m{i - 1}"
        if schema != "main":
            con.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
        con.deserialize(_FUTURES.pop(name).result(), name=schema)
    con.execute("PRAGMA query_only = ON")
    from backend import memdb

    memdb.CONN = con
    _POOL.shutdown(wait=False)
    return {"version": _MANIFEST.get("version"), "boot_seconds": round(time.time() - _T0, 1), **_PHASE, "shards_ready_s": round(time.time() - _T0, 2)}


BOOT = boot()


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
