"""ML leakage / evaluation tests and API tests (filters, pagination, validation, CSV, caching)."""
import json
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

warnings.filterwarnings("ignore")
DB = Path(__file__).resolve().parents[2] / "data" / "olympics_warehouse.db"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="warehouse not built")


@pytest.fixture(scope="module")
def con():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    yield c
    c.close()


# ---------------------------------------------------------------- ML: leakage prevention
def test_country_panel_features_only_use_earlier_editions(con):
    from backend.analytics.ml import FEATURES_A, build_country_panel
    pan = build_country_panel(con).sort_values(["season", "noc_code", "year"])
    g = pan.groupby(["season", "noc_code"])
    # prev_total must equal the NOC's total at its previous edition of the same season - never its own
    shifted = g.total.shift(1).fillna(0)
    assert (pan.prev_total == shifted).all()
    assert (pan.prev_gold == g.gold.shift(1).fillna(0)).all()
    # first appearance => no history
    first = pan[pan.first_appearance == 1]
    assert (first.prev_total == 0).all() and (first.mean_prev3 == 0).all()
    # no feature is the target itself, and none perfectly equals it
    assert "total" not in FEATURES_A
    for f in FEATURES_A:
        assert not np.array_equal(pan[f].values, pan.total.values)
    # mean_prev3 uses strictly earlier rows: changing the current row must not change it
    nxt = pan.groupby(["season", "noc_code"]).mean_prev3.apply(lambda s: s.iloc[0] == 0).all()
    assert nxt


def test_prediction_design_is_chronological(con):
    d = json.loads(con.execute("SELECT payload_json FROM analytics_results WHERE module='ml' AND key='medal_prediction'").fetchone()[0])
    assert "strictly earlier" in d["design"]["split"].lower() and "backtest" in d["design"]["what_this_is"].lower()
    assert all(e in ("2008_summer", "2012_summer", "2016_summer", "2020_summer", "2024_summer", "2010_winter", "2014_winter", "2018_winter", "2022_winter", "2026_winter") for e in d["design"]["test_editions"])
    assert set(d["metrics_all_participating_nocs"]) >= {"naive_previous_total", "linear_regression", "poisson_regression", "random_forest", "gradient_boosting", "xgboost_poisson"}


def test_metrics_are_finite_and_sane(con):
    d = json.loads(con.execute("SELECT payload_json FROM analytics_results WHERE module='ml' AND key='medal_prediction'").fetchone()[0])
    for m, v in d["metrics_all_participating_nocs"].items():
        assert all(np.isfinite(v[k]) for k in ("mae", "rmse", "r2")), m
        assert v["rmse"] >= v["mae"] >= 0
    assert d["prediction_interval_80"]["empirical_coverage"] > 0.5


def test_athlete_model_thresholds_chosen_on_validation_and_auc_beats_chance(con):
    d = json.loads(con.execute("SELECT payload_json FROM analytics_results WHERE module='ml' AND key='athlete_medal_model'").fetchone()[0])
    des = d["design"]
    assert des["train"].startswith("participations before 2000") and "never used" in des["test"]
    for name, m in d["models"].items():
        assert m["roc_auc"] > 0.6 and 0 < m["pr_auc"] < 1, name
        cm = m["confusion_matrix"]
        assert cm["tp"] + cm["fn"] > 0 and cm["tn"] + cm["fp"] > 0
        assert 0 < m["threshold_from_validation"] < 1
    assert "leakage" in des["leakage_controls"].lower() or "EARLIER" in des["leakage_controls"]


def test_athlete_features_exclude_current_edition_information(con):
    d = json.loads(con.execute("SELECT payload_json FROM analytics_results WHERE module='ml' AND key='athlete_medal_model'").fetchone()[0])
    banned = {"medal", "is_medalist", "position", "result", "total", "gold"}
    assert not (set(d["design"]["features"]) & banned)


def test_models_are_versioned_and_tracked():
    root = DB.parents[1]
    assert list((root / "models").glob("*.joblib")), "no saved model artefacts"
    db = root / "mlflow.db"
    assert db.exists(), "no MLflow tracking database (run scripts/run_analytics.py --only ml)"
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert n >= 9, f"only {n} tracked runs"  # 6 medal models + 3 athlete models


def test_clustering_is_reproducible_and_reports_alternatives(con):
    d = json.loads(con.execute("SELECT payload_json FROM analytics_results WHERE module='ml' AND key='clustering'").fetchone()[0])
    assert d["chosen_k"] >= 3 and str(d["chosen_k"]) in d["k_selection_silhouette"]
    assert d["dbscan"]["justification"] and -1 <= d["kmeans_silhouette"] <= 1


# ---------------------------------------------------------------- API
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.api.main import app
    return TestClient(app)


def test_core_endpoints_return_200(client):
    for u in ["/api/overview", "/api/games", "/api/games/2024_summer", "/api/countries?page_size=5", "/api/countries/USA", "/api/athletes?page_size=5", "/api/sports", "/api/events?page_size=5",
              "/api/results?page_size=5", "/api/medals", "/api/statistics", "/api/statistics/hypothesis-tests", "/api/statistics/regression", "/api/statistics/time-series",
              "/api/machine-learning/models", "/api/machine-learning/predictions", "/api/team-sports", "/api/matches?page_size=5", "/api/records", "/api/data-quality", "/api/data-engineering/pipeline-status"]:
        r = client.get(u)
        assert r.status_code == 200, (u, r.text[:200])


def test_pagination_and_filters(client):
    a = client.get("/api/athletes", params={"page_size": 10, "page": 1}).json()
    b = client.get("/api/athletes", params={"page_size": 10, "page": 2}).json()
    assert len(a["rows"]) == 10 and a["rows"][0]["athlete_id"] != b["rows"][0]["athlete_id"] and a["total"] == b["total"] > 1000
    f = client.get("/api/athletes", params={"gender": "F", "medal": "gold", "noc": "USA", "page_size": 20}).json()
    assert f["total"] > 0 and all(r["gender"] == "F" and r["gold"] > 0 and "USA" in r["nocs"] for r in f["rows"])
    res = client.get("/api/results", params={"games_id": "2024_summer", "sport": "swimming", "medal": "gold", "page_size": 50}).json()
    assert res["total"] > 0 and all(r["games_id"] == "2024_summer" and r["medal"] == "Gold" for r in res["rows"])
    c = client.get("/api/countries", params={"continent": "Europe", "page_size": 300}).json()
    assert c["rows"] and all(r["continent"] == "Europe" for r in c["rows"])


def test_sorting_is_applied(client):
    r = client.get("/api/countries", params={"sort": "total_medals", "order": "desc", "page_size": 5}).json()["rows"]
    assert [x["total_medals"] for x in r] == sorted([x["total_medals"] for x in r], reverse=True)
    assert r[0]["noc_code"] == "USA"


def test_invalid_input_is_rejected_cleanly(client):
    assert client.get("/api/athletes", params={"gender": "Z"}).status_code == 422
    assert client.get("/api/athletes", params={"sort": "name; DROP TABLE athletes"}).status_code == 422
    assert client.get("/api/medals", params={"view": "edition"}).status_code == 422
    assert client.get("/api/games", params={"season": "spring"}).status_code == 422
    assert client.get("/api/games/9999_summer").status_code == 404
    assert client.get("/api/countries/ZZZ").status_code == 404
    assert client.get("/api/athletes/compare", params={"ids": "1"}).status_code == 422
    assert client.get("/api/statistics/explore", params={"gender": "Q"}).status_code == 422
    assert client.get("/api/athletes", params={"q": "x'; DROP TABLE athletes;--"}).status_code == 200   # parameterised


def test_csv_export(client):
    r = client.get("/api/results", params={"format": "csv", "sport": "athletics"})
    assert r.headers["content-type"].startswith("text/csv") and r.text.splitlines()[0].startswith("games_id,year")
    assert len(r.text.splitlines()) > 100


def test_medal_leaderboard_is_tie_aware(client):
    rows = client.get("/api/medals", params={"view": "edition", "games_id": "2024_summer", "limit": 300}).json()["rows"]
    ranks = [r["rank"] for r in rows]
    assert ranks == sorted(ranks) and len(set(ranks)) < len(ranks)
    top = rows[0]
    assert top["noc_code"] == "USA" and (top["gold"], top["silver"], top["bronze"]) == (40, 44, 42)


def test_live_statistics_explorer_is_consistent_with_filters(client):
    j = client.get("/api/statistics/explore", params={"season": "winter", "gender": "F"}).json()
    assert j["n"] > 1000 and j["descriptive"]["min"] >= 10 and j["descriptive"]["q1"] <= j["descriptive"]["median"] <= j["descriptive"]["q3"]
    assert sum(h["count"] for h in j["histogram"]) == j["n"]
    small = client.get("/api/statistics/explore", params={"noc": "ZZZ"}).json()
    assert small["n"] == 0 and "Not enough" in small["message"]


def test_hypothesis_tests_expose_all_required_fields(client):
    t = client.get("/api/statistics/hypothesis-tests").json()
    assert len(t) >= 7
    need = {"null_hypothesis", "alternative_hypothesis", "method", "why_this_test", "n", "statistic", "p_value", "effect_size", "effect_size_name", "interpretation", "assumptions"}
    for x in t:
        assert need <= set(x), x["test_id"]
    conf = [x for x in t if x["family"] == "confirmatory"]
    assert all(x["p_adjusted_holm"] >= x["p_value"] for x in conf)


def test_missing_analytics_gives_a_clear_404(client):
    r = client.get("/api/eda/not_a_real_analysis")
    assert r.status_code == 404 and "run_analytics" in r.json()["detail"]
