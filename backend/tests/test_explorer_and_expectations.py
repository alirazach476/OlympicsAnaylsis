import sqlite3
from pathlib import Path

import pytest

DB = Path(__file__).resolve().parents[2] / "data" / "olympics_warehouse.db"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="warehouse not built")


def test_expectations_run_and_only_known_gaps_fail():
    from backend.validators.expectations import run_all

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    res = {r["check"]: r for r in run_all(con)}
    assert not any("check error" in r["detail"] for r in res.values())
    failing = {k for k, r in res.items() if not r["passed"]}
    assert failing <= {"pictograms_for_every_game"}, failing


def test_explorer_rejects_unknown_table_and_paginates():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    c = TestClient(app)
    assert c.get("/api/explorer/sqlite_master").status_code == 404
    r = c.get("/api/explorer/medals", params={"page_size": 5})
    assert r.status_code == 200 and len(r.json()["rows"]) == 5 and r.json()["total"] > 5
    assert c.get("/api/explorer/athletes", params={"q": "x'; DROP TABLE athletes;--"}).status_code == 200
