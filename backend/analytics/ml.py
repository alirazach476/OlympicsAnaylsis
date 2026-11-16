"""PHASE 5 - machine learning with chronological validation (no leakage) and MLflow tracking.

A. country medal prediction   B. athlete medal probability   C. country clustering   D. sport specialization   E. interpretability.
Everything is a HISTORICAL BACKTEST: models are trained only on editions strictly before the edition they predict. No claim of future accuracy.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.linear_model import LinearRegression, LogisticRegression, PoissonRegressor
from scipy.cluster.hierarchy import dendrogram as _dendrogram, linkage as _linkage
from sklearn.metrics import (precision_recall_curve, roc_curve, average_precision_score, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score,
                             recall_score, roc_auc_score, silhouette_score, adjusted_rand_score, brier_score_loss)
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from xgboost import XGBClassifier, XGBRegressor

from .store import ROOT, save

warnings.filterwarnings("ignore")
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)
SEED = 42

HAVE_MLFLOW = False
try:
    import mlflow
    # MLflow 3 deprecates the plain file store; tracking goes to a SQLite database, artefacts to ./mlruns
    mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}")
    if mlflow.get_experiment_by_name("olympics-sports-intelligence") is None:
        mlflow.create_experiment("olympics-sports-intelligence", artifact_location=(ROOT / "mlruns").as_uri())
    mlflow.set_experiment("olympics-sports-intelligence")
    HAVE_MLFLOW = True
except Exception as exc:  # noqa: BLE001
    import sys
    print(f"WARNING: MLflow tracking unavailable ({exc}); runs will not be tracked", file=sys.stderr)


def track(run_name: str, params: dict, metrics: dict, artifact: Path | None = None):
    if not HAVE_MLFLOW:
        return None
    with mlflow.start_run(run_name=run_name) as r:
        mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None and np.isfinite(v)})
        if artifact and artifact.exists():
            mlflow.log_artifact(str(artifact))
        return r.info.run_id


def data_version(con) -> str:
    r = con.execute("SELECT COUNT(*), COALESCE(MAX(participation_id),0) FROM silver_participations").fetchone()
    return hashlib.sha1(json.dumps(r).encode()).hexdigest()[:10]


# =========================================================================================== A. country medal prediction
FEATURES_A = ["prev_total", "prev_gold", "prev_silver", "prev_bronze", "mean_prev3", "prev_athletes", "appearance_no", "first_appearance", "is_host", "athletes", "sports", "is_winter", "prev_share"]


def build_country_panel(con) -> pd.DataFrame:
    """One row per (NOC, edition). All 'prev_*' features come from EARLIER editions of the same season only (shift within NOC/season).
    `athletes` and `sports` are the delegation size/breadth entered for that edition - known from the entry lists before competition,
    but flagged in the output as entry-list-time information."""
    part = pd.read_sql("SELECT athlete_id, games_id, year, season, noc_code, sport_name FROM silver_participations", con)
    pan = part.groupby(["games_id", "year", "season", "noc_code"]).agg(athletes=("athlete_id", "nunique"), sports=("sport_name", "nunique")).reset_index()
    cm = pd.read_sql("SELECT games_id, noc_code, gold, silver, bronze, total FROM silver_country_medals", con)
    pan = pan.merge(cm, on=["games_id", "noc_code"], how="left").fillna({"gold": 0, "silver": 0, "bronze": 0, "total": 0})
    host = pd.read_sql("SELECT games_id, host_noc FROM ref_host_noc", con)
    pan = pan.merge(host, on="games_id", how="left")
    pan["is_host"] = (pan.noc_code == pan.host_noc).astype(int)
    pan["is_winter"] = (pan.season == "winter").astype(int)
    pan = pan.sort_values(["season", "noc_code", "year"]).reset_index(drop=True)
    g = pan.groupby(["season", "noc_code"])
    for c in ("total", "gold", "silver", "bronze", "athletes"):
        pan[f"prev_{c}"] = g[c].shift(1)
    pan["mean_prev3"] = g.total.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    pan["appearance_no"] = g.cumcount()
    pan["first_appearance"] = (pan.appearance_no == 0).astype(int)
    edtot = pan.groupby("games_id").total.transform("sum")
    pan["share"] = pan.total / edtot
    pan["prev_share"] = pan.groupby(["season", "noc_code"]).share.shift(1)
    for c in ("prev_total", "prev_gold", "prev_silver", "prev_bronze", "mean_prev3", "prev_athletes", "prev_share"):
        pan[c] = pan[c].fillna(0)  # never-medalled / first-time NOCs get 0 history (flagged by first_appearance)
    return pan


def _metrics(y, p):
    p = np.clip(p, 0, None)
    return {"mae": mean_absolute_error(y, p), "rmse": float(np.sqrt(mean_squared_error(y, p))), "r2": r2_score(y, p)}


def medal_prediction(con, ver: str):
    pan = build_country_panel(con)
    # rolling-origin (expanding window): every test edition is predicted by models trained only on strictly earlier editions
    test_games = ["2008_summer", "2012_summer", "2016_summer", "2020_summer", "2024_summer", "2010_winter", "2014_winter", "2018_winter", "2022_winter", "2026_winter"]
    order = pan[["games_id", "year"]].drop_duplicates().set_index("games_id").year
    makers = {
        "naive_previous_total": None,
        "linear_regression": lambda: make_pipeline(StandardScaler(), LinearRegression()),
        "poisson_regression": lambda: make_pipeline(FunctionTransformer(np.log1p, validate=False), StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=1000)),  # log1p inputs: the exp link otherwise extrapolates wildly
        "random_forest": lambda: RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=SEED, n_jobs=-1),
        "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=.05, subsample=.8, random_state=SEED),
        "xgboost_poisson": lambda: XGBRegressor(n_estimators=300, max_depth=3, learning_rate=.05, subsample=.8, objective="count:poisson", random_state=SEED, n_jobs=4),
    }
    preds = {m: [] for m in makers}
    pi_low, pi_high, rows = [], [], []
    for tg in test_games:
        te = pan[pan.games_id == tg]
        tr = pan[(pan.year < order[tg]) | ((pan.year == order[tg]) & (pan.games_id != tg) & False)]
        tr = tr[(tr.year < order[tg])]  # strictly earlier editions (both seasons: season is a feature)
        assert tr.year.max() < te.year.min(), "leakage: training data must precede the tested edition"
        rows.append(te[["games_id", "noc_code", "total"]])
        for m, mk in makers.items():
            preds[m].append(te.prev_total.values.astype(float) if mk is None else np.clip(mk().fit(tr[FEATURES_A], tr.total).predict(te[FEATURES_A]), 0, None))
        lo = GradientBoostingRegressor(loss="quantile", alpha=.1, n_estimators=200, max_depth=3, random_state=SEED).fit(tr[FEATURES_A], tr.total)
        hi = GradientBoostingRegressor(loss="quantile", alpha=.9, n_estimators=200, max_depth=3, random_state=SEED).fit(tr[FEATURES_A], tr.total)
        pi_low.append(np.clip(lo.predict(te[FEATURES_A]), 0, None)); pi_high.append(np.clip(hi.predict(te[FEATURES_A]), 0, None))
    res = pd.concat(rows, ignore_index=True)
    y = res.total.values
    summary = {m: _metrics(y, np.concatenate(v)) for m, v in preds.items()}
    lo, hi = np.concatenate(pi_low), np.concatenate(pi_high)
    summary_pi = {"nominal": 0.8, "empirical_coverage": float(((y >= lo) & (y <= hi)).mean()), "mean_width": float((hi - lo).mean()),
                  "note": "quantile gradient boosting (10th-90th percentile); under-coverage is typical for count targets with heavy tails"}
    # medal-winning NOCs only (the harder, more interesting subset)
    win = y > 0
    summary_winners = {m: _metrics(y[win], np.concatenate(v)[win]) for m, v in preds.items()}
    best = min((m for m in summary if m != "naive_previous_total"), key=lambda m: summary[m]["rmse"])
    res["pred_best"] = np.concatenate(preds[best]); res["pi_low"] = lo; res["pi_high"] = hi; res["pred_naive"] = np.concatenate(preds["naive_previous_total"])
    avp = res.sort_values("total", ascending=False)
    per_ed = [{"games_id": g, **_metrics(d.total.values, d.pred_best.values), "naive_rmse": _metrics(d.total.values, d.pred_naive.values)["rmse"], "n": int(len(d))} for g, d in res.groupby("games_id")]

    # final model on the full last window (train < 2024 summer / 2026 winter) for interpretability
    last_summer, last_winter = pan[pan.games_id == "2024_summer"], pan[pan.games_id == "2026_winter"]
    test = pd.concat([last_summer, last_winter])
    train = pan[~pan.games_id.isin(["2024_summer", "2026_winter"])]
    train = train[train.year < 2024]
    xgb = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=.05, subsample=.8, objective="count:poisson", random_state=SEED, n_jobs=4).fit(train[FEATURES_A], train.total)
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=SEED, n_jobs=-1).fit(train[FEATURES_A], train.total)
    perm = permutation_importance(rf, test[FEATURES_A], test.total, n_repeats=15, random_state=SEED, scoring="neg_mean_absolute_error")
    interp = {"permutation_importance_rf": pd.DataFrame({"feature": FEATURES_A, "importance_mae": perm.importances_mean, "std": perm.importances_std}).sort_values("importance_mae", ascending=False),
              "feature_importance_xgboost_gain": dict(zip(FEATURES_A, map(float, xgb.feature_importances_)))}
    try:
        import shap
        sv = shap.TreeExplainer(xgb).shap_values(test[FEATURES_A])
        interp["shap_mean_abs_xgboost"] = dict(zip(FEATURES_A, map(float, np.abs(sv).mean(0))))
        top = test.assign(pred=xgb.predict(test[FEATURES_A])).sort_values("total", ascending=False).head(8)
        interp["shap_examples"] = [{"games_id": r.games_id, "noc": r.noc_code, "actual": float(r.total), "predicted": float(r.pred),
                                    "contributions": dict(zip(FEATURES_A, map(float, sv[i])))} for i, (_, r) in enumerate(top.iterrows()) if False] or [
            {"games_id": test.iloc[i].games_id, "noc": test.iloc[i].noc_code, "actual": float(test.iloc[i].total), "contributions": dict(zip(FEATURES_A, map(float, sv[i])))}
            for i in np.argsort(-test.total.values)[:8]]
    except Exception as e:  # noqa: BLE001
        interp["shap_error"] = str(e)
    pdp = {}
    for f in ("prev_total", "athletes", "is_host"):
        r = partial_dependence(rf, train[FEATURES_A].sample(3000, random_state=1).astype(float), [f], grid_resolution=15)
        pdp[f] = {"x": r["grid_values"][0], "y": r["average"][0]}
    interp["partial_dependence_rf"] = pdp
    ver_tag = f"{ver}-{dt.datetime.now().strftime('%Y%m%d')}"
    path = MODELS / f"medal_xgb_{ver_tag}.joblib"
    joblib.dump({"model": xgb, "features": FEATURES_A, "trained_before": "2024_summer/2026_winter", "data_version": ver}, path)
    for m, s in summary.items():
        track(f"medal_prediction/{m}", {"models": m, "features": FEATURES_A, "test": test_games, "data_version": ver}, s, path if m == "xgboost_poisson" else None)
    save(con, "ml", "medal_prediction", "Country medal prediction (historical backtest)", {
        "design": {"split": "Expanding-window, chronological. Each test edition is predicted by models trained ONLY on strictly earlier editions (assertion enforced in code).",
                   "test_editions": test_games, "target": "total medals in the official medal table (0 for participating NOCs without a medal)",
                   "features": FEATURES_A, "entry_list_time_features": ["athletes", "sports"], "leakage_controls": "prev_* use only earlier editions of the same season; NOCs with no history get 0 and first_appearance=1",
                   "what_this_is": "BACKTEST on past editions - not a forecast of any future Games.", "n_predictions": int(len(res))},
        "metrics_all_participating_nocs": summary, "metrics_medal_winning_nocs_only": summary_winners, "best_model_by_rmse": best, "prediction_interval_80": summary_pi, "per_edition_best_model": per_ed,
        "actual_vs_predicted_top": avp.head(60)[["games_id", "noc_code", "total", "pred_best", "pi_low", "pi_high", "pred_naive"]],
        "actual_vs_predicted_sample": res.sample(400, random_state=2)[["games_id", "noc_code", "total", "pred_best"]], "interpretability": interp,
        "model_version": ver_tag, "caveat": "Medals depend on events outside this feature set (new sports, boycotts, doping reallocations, NOC splits)."},
        "Can past performance and delegation size predict a country's medal count at an edition it has not yet seen?")
    return {"best": best, "summary": summary}


# =========================================================================================== B. athlete medal probability
def athlete_model(con, ver: str):
    d = pd.read_sql("SELECT athlete_id, games_id, year, season, noc_code, gender, age, sport_name, is_medalist, is_host_noc FROM silver_participations "
                    "WHERE age IS NOT NULL AND gender IN ('M','F')", con)
    d = d.sort_values(["athlete_id", "year"]).reset_index(drop=True)
    # prior Games count / prior medal count: strictly earlier Games of the same athlete
    gm = d.groupby(["athlete_id", "year", "games_id"]).is_medalist.sum().reset_index().sort_values(["athlete_id", "year"])
    gm["prior_games"] = gm.groupby("athlete_id").cumcount()
    gm["prior_medals"] = gm.groupby("athlete_id").is_medalist.cumsum() - gm.is_medalist
    d = d.merge(gm[["athlete_id", "games_id", "prior_games", "prior_medals"]], on=["athlete_id", "games_id"], how="left")

    def prior_rate(keys, k=10, mu=None):
        e = d.groupby(keys + ["year"]).is_medalist.agg(["sum", "count"]).reset_index().sort_values(keys + ["year"])
        cs = e.groupby(keys)[["sum", "count"]].cumsum() - e[["sum", "count"]]  # excludes the current edition
        mu = mu if mu is not None else float(d.is_medalist.mean())
        e["rate"] = (cs["sum"] + mu * k) / (cs["count"] + k)
        e["n_prior"] = cs["count"]
        return e[keys + ["year", "rate", "n_prior"]]
    d = d.merge(prior_rate(["noc_code", "season"]).rename(columns={"rate": "noc_prior_rate", "n_prior": "noc_prior_n"}), on=["noc_code", "season", "year"], how="left")
    d = d.merge(prior_rate(["sport_name", "season"]).rename(columns={"rate": "sport_prior_rate", "n_prior": "sport_prior_n"}), on=["sport_name", "season", "year"], how="left")
    d["is_female"] = (d.gender == "F").astype(int); d["is_winter"] = (d.season == "winter").astype(int)
    d["age_sq"] = d.age ** 2
    feats = ["age", "age_sq", "is_female", "is_winter", "prior_games", "prior_medals", "noc_prior_rate", "noc_prior_n", "sport_prior_rate", "is_host_noc"]
    train, val, test = d[d.year < 2000], d[(d.year >= 2000) & (d.year < 2008)], d[d.year >= 2008]
    assert train.year.max() < val.year.min() and val.year.max() < test.year.min()
    models = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=1.0)),
        "random_forest": RandomForestClassifier(n_estimators=250, max_depth=10, min_samples_leaf=50, n_jobs=-1, random_state=SEED, class_weight="balanced_subsample"),
        "xgboost": XGBClassifier(n_estimators=300, max_depth=4, learning_rate=.06, subsample=.8, colsample_bytree=.8, eval_metric="logloss", random_state=SEED, n_jobs=4),
    }
    out, fitted, curves = {}, {}, {}
    for name, m in models.items():
        m.fit(train[feats], train.is_medalist)
        pv = m.predict_proba(val[feats])[:, 1]
        ths = np.linspace(.05, .8, 76)
        th = float(ths[int(np.argmax([f1_score(val.is_medalist, pv >= t) for t in ths]))])  # threshold chosen on VALIDATION only
        pt = m.predict_proba(test[feats])[:, 1]
        yhat = pt >= th
        cm = confusion_matrix(test.is_medalist, yhat)
        bins = np.linspace(0, 1, 11)
        cal = pd.DataFrame({"bin": pd.cut(pt, bins, include_lowest=True), "p": pt, "y": test.is_medalist.values}).groupby("bin", observed=True).agg(mean_predicted=("p", "mean"), observed_rate=("y", "mean"), n=("y", "size")).reset_index()
        cal["bin"] = cal["bin"].astype(str)
        out[name] = {"threshold_from_validation": th, "precision": precision_score(test.is_medalist, yhat), "recall": recall_score(test.is_medalist, yhat), "f1": f1_score(test.is_medalist, yhat),
                     "roc_auc": roc_auc_score(test.is_medalist, pt), "pr_auc": average_precision_score(test.is_medalist, pt), "brier": brier_score_loss(test.is_medalist, pt),
                     "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}, "calibration": cal}
        fpr, tpr, _ = roc_curve(test.is_medalist, pt)
        pr_p, pr_r, _ = precision_recall_curve(test.is_medalist, pt)
        ri = np.unique(np.linspace(0, len(fpr) - 1, 200).astype(int)); pi = np.unique(np.linspace(0, len(pr_p) - 1, 200).astype(int))
        curves[name] = {"roc": {"fpr": fpr[ri], "tpr": tpr[ri]}, "pr": {"recall": pr_r[pi], "precision": pr_p[pi]}}
        fitted[name] = m
        track(f"athlete_medal/{name}", {"features": feats, "train": "<2000", "val": "2000-2007", "test": ">=2008", "data_version": ver}, {k: v for k, v in out[name].items() if isinstance(v, float)})
    base = float(test.is_medalist.mean())
    best = max(out, key=lambda k: out[k]["pr_auc"])
    perm = permutation_importance(fitted[best], test.sample(30000, random_state=1)[feats], test.sample(30000, random_state=1).is_medalist, n_repeats=5, random_state=SEED, scoring="average_precision")
    interp = {"permutation_importance_best": pd.DataFrame({"feature": feats, "importance_pr_auc": perm.importances_mean}).sort_values("importance_pr_auc", ascending=False)}
    try:
        import shap
        ex = shap.TreeExplainer(fitted["xgboost"])
        smp = test.sample(4000, random_state=2)[feats]
        sv = ex.shap_values(smp)
        interp["shap_mean_abs_xgboost"] = dict(zip(feats, map(float, np.abs(sv).mean(0))))
        k = min(1500, len(smp))
        interp["shap_sample_xgboost"] = {"features": feats, "base_value": float(np.ravel(ex.expected_value)[0]), "values": smp.iloc[:k][feats].round(4).values.tolist(), "shap": np.round(sv[:k], 5).tolist(),
                                         "note": "SHAP values of the XGBoost model (log-odds scale) for a random sample of test-period participations"}
    except Exception as e:  # noqa: BLE001
        interp["shap_error"] = str(e)
    # learning curve: XGBoost PR-AUC on the validation set as the training set grows
    lc = []
    for frac in (0.1, 0.2, 0.4, 0.6, 0.8, 1.0):
        sub = train.sample(frac=frac, random_state=SEED) if frac < 1 else train
        mm = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=.06, subsample=.8, colsample_bytree=.8, eval_metric="logloss", random_state=SEED, n_jobs=4).fit(sub[feats], sub.is_medalist)
        lc.append({"train_fraction": frac, "n_train": int(len(sub)), "train_pr_auc": float(average_precision_score(sub.is_medalist, mm.predict_proba(sub[feats])[:, 1])),
                   "validation_pr_auc": float(average_precision_score(val.is_medalist, mm.predict_proba(val[feats])[:, 1]))})
    # chronological expanding-window cross-validation (each fold trains only on strictly earlier Games)
    cv = []
    for lo, hi in ((1992, 2000), (2000, 2008), (2008, 2016), (2016, 2027)):
        tr_, te_ = d[d.year < lo], d[(d.year >= lo) & (d.year < hi)]
        if tr_.is_medalist.nunique() < 2 or te_.is_medalist.nunique() < 2:
            continue
        cvm = {"logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
               "random_forest": RandomForestClassifier(n_estimators=120, max_depth=10, min_samples_leaf=50, n_jobs=-1, random_state=SEED, class_weight="balanced_subsample"),
               "xgboost": XGBClassifier(n_estimators=200, max_depth=4, learning_rate=.08, subsample=.8, colsample_bytree=.8, eval_metric="logloss", random_state=SEED, n_jobs=4)}
        for nm_, mm in cvm.items():
            mm.fit(tr_[feats], tr_.is_medalist); pp = mm.predict_proba(te_[feats])[:, 1]
            cv.append({"fold": f"test {lo}-{min(hi, 2026)}", "model": nm_, "n_train": int(len(tr_)), "n_test": int(len(te_)),
                       "roc_auc": float(roc_auc_score(te_.is_medalist, pp)), "pr_auc": float(average_precision_score(te_.is_medalist, pp)), "base_rate": float(te_.is_medalist.mean())})
    path = MODELS / f"athlete_medal_xgb_{ver}-{dt.datetime.now().strftime('%Y%m%d')}.joblib"
    joblib.dump({"model": fitted["xgboost"], "features": feats, "threshold": out["xgboost"]["threshold_from_validation"]}, path)
    save(con, "ml", "athlete_medal_model", "Athlete medal probability (chronological validation)", {
        "design": {"train": "participations before 2000", "validation": "2000-2007 (decision threshold chosen here)", "test": "2008-2026 (never used for fitting or threshold)", "features": feats,
                   "n_train": int(len(train)), "n_val": int(len(val)), "n_test": int(len(test)), "base_rate_test": base,
                   "leakage_controls": "prior_games, prior_medals, noc_prior_rate, sport_prior_rate are computed only from EARLIER Games; no event result or same-edition NOC/sport medal data is used."},
        "models": out, "best_model_by_pr_auc": best, "interpretability": interp, "curves": curves, "learning_curve": lc, "cross_validation": cv,
        "bias_notes": ["Selection bias: only athletes who reached the recorded entry/result lists appear; qualification is itself a performance filter.",
                       "The label counts every member of a medal-winning team, so team sports inflate the positive rate.",
                       "Age is available for ~99.6% of participations but height/weight are sparse, so body measurements are not used.",
                       "Athlete-level data are incomplete for some editions and some athletes are unmatched across sources."],
        "model_version": f"{ver}-{dt.datetime.now().strftime('%Y%m%d')}"}, "Can pre-event information estimate the probability that a participation ends in a medal?")
    return {"best": best, "pr_auc": out[best]["pr_auc"]}


# =========================================================================================== C/D. clustering + specialization
def clustering(con):
    h = pd.read_sql("SELECT * FROM gold_country_participation_history WHERE appearances>=3", con)
    aw = pd.read_sql("SELECT a.noc_code, a.sport_name, g.season, COUNT(*) m FROM silver_medal_awards a JOIN games g USING(games_id) GROUP BY 1,2,3", con)
    tot = aw.groupby("noc_code").m.sum().rename("awards")
    sp = aw.groupby(["noc_code", "sport_name"]).m.sum().reset_index()
    sp["share"] = sp.m / sp.groupby("noc_code").m.transform("sum")
    hhi = sp.groupby("noc_code").share.apply(lambda s: float((s ** 2).sum())).rename("sport_hhi")
    top = sp.sort_values("share", ascending=False).drop_duplicates("noc_code").set_index("noc_code")
    win = aw.groupby(["noc_code", "season"]).m.sum().unstack(fill_value=0)
    df = h.set_index("noc_code").join(tot).join(hhi).join(win).fillna({"awards": 0, "sport_hhi": 1, "summer": 0, "winter": 0})
    df["winter_share"] = df.winter / (df.summer + df.winter).replace(0, np.nan)
    df["winter_share"] = df.winter_share.fillna(0)
    df["medals_per_appearance"] = df.total_medals / df.appearances
    df["gold_ratio"] = (df.gold / df.total_medals.replace(0, np.nan)).fillna(0)
    df["log_total_medals"] = np.log1p(df.total_medals)
    df["athletes_per_appearance"] = df.athletes / df.appearances
    df["n_medal_sports"] = sp.groupby("noc_code").sport_name.nunique().reindex(df.index).fillna(0)
    feats = ["log_total_medals", "medals_per_appearance", "gold_ratio", "winter_share", "sport_hhi", "n_medal_sports", "appearances", "athletes_per_appearance"]
    X = StandardScaler().fit_transform(df[feats])
    sil, inertia = {}, {}
    for k in range(2, 11):
        kmk = KMeans(k, n_init=20, random_state=SEED).fit(X)
        inertia[k] = float(kmk.inertia_)
        if 3 <= k <= 8:  # k=2 only re-creates the medal-volume split, so the silhouette search is 3..8 (k up to 10 is stored for the elbow plot only)
            sil[k] = float(silhouette_score(X, kmk.labels_))
    k = max(sil, key=sil.get)
    km = KMeans(k, n_init=50, random_state=SEED).fit(X)
    hc = AgglomerativeClustering(k, linkage="ward").fit(X)
    pca = PCA(3, random_state=SEED).fit(X)
    xy = pca.transform(X)
    nn = NearestNeighbors(n_neighbors=5).fit(X)
    kd = np.sort(nn.kneighbors(X)[0][:, -1])
    eps = float(np.percentile(kd, 90))
    db = DBSCAN(eps=eps, min_samples=5).fit(X)
    df["cluster"], df["hc_cluster"], df["db_cluster"] = km.labels_, hc.labels_, db.labels_
    df["pc1"], df["pc2"], df["pc3"] = xy[:, 0], xy[:, 1], xy[:, 2]
    dg = _dendrogram(_linkage(X, "ward"), no_plot=True, labels=list(df.index))
    prof = df.groupby("cluster")[feats + ["total_medals"]].mean().round(3)
    prof["n_nocs"] = df.groupby("cluster").size()
    prof["examples"] = df.sort_values("total_medals", ascending=False).groupby("cluster").apply(lambda g: g.index[:6].tolist(), include_groups=False)
    z = pd.DataFrame(StandardScaler().fit_transform(df[feats]), index=df.index, columns=feats).groupby(df.cluster).mean()
    prof["distinguishing_features"] = z.apply(lambda r: [f"{c} ({v:+.1f} sd)" for c, v in r.abs().sort_values(ascending=False).head(3).items() for v in [r[c]]], axis=1)
    save(con, "ml", "clustering", "Country performance clustering", {
        "features": feats, "n_nocs": int(len(df)), "inclusion_rule": "NOCs with >=3 Games appearances", "k_selection_silhouette": sil, "inertia_by_k": inertia, "chosen_k": k, "dendrogram": {"icoord": dg["icoord"], "dcoord": dg["dcoord"], "leaves": dg["ivl"], "linkage": "ward"},
        "kmeans_silhouette": sil[k], "hierarchical_vs_kmeans_adjusted_rand": float(adjusted_rand_score(km.labels_, hc.labels_)),
        "dbscan": {"eps": eps, "min_samples": 5, "clusters": int(len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)), "noise_points": int((db.labels_ == -1).sum()),
                   "justification": "density-based check: DBSCAN is reported to show whether natural dense groups exist; it is not used for the main grouping because medal data is continuous and heavy-tailed"},
        "pca": {"explained_variance_ratio": pca.explained_variance_ratio_, "loadings": pd.DataFrame(pca.components_.T, index=feats, columns=["pc1", "pc2", "pc3"])},
        "cluster_profiles": prof.reset_index(), "points": df.reset_index()[["noc_code", "historical_name", "cluster", "hc_cluster", "db_cluster", "pc1", "pc2", "pc3", "total_medals", "appearances"]],
        "note": "Clusters are described by their feature means and most distinguishing standardised features; no subjective names are assigned."}, "Which groups of countries have similar Olympic profiles?")

    spz = df.reset_index()[["noc_code", "historical_name", "sport_hhi", "winter_share", "n_medal_sports", "total_medals"]].merge(
        top.reset_index()[["noc_code", "sport_name", "share"]].rename(columns={"sport_name": "dominant_sport", "share": "dominant_sport_share"}), on="noc_code", how="left")
    spz["profile"] = np.select([spz.winter_share >= .7, spz.winter_share <= .05, spz.sport_hhi >= .35], ["winter-focused", "summer-only medals", "concentrated in few sports"], "diversified / mixed")
    dom = sp.merge(aw.groupby("sport_name").m.sum().rename("sport_total"), on="sport_name").query("m>=5 and share>=0.15").sort_values("m", ascending=False)
    save(con, "ml", "sport_specialization", "Sport specialization", {
        "countries": spz[spz.total_medals > 0].sort_values("sport_hhi", ascending=False), "dominant_country_sport_pairs": dom.head(60),
        "definition": "sport_hhi = sum of squared shares of an NOC's medals across sports (1 = single sport). winter_share = share of its medal awards won in Winter Games."}, "Which countries specialise, and in what?")
    return {"k": k, "silhouette": sil[k]}


def run(con):
    ver = data_version(con)
    out = {"medal_prediction": medal_prediction(con, ver), "athlete_model": athlete_model(con, ver), "clustering": clustering(con)}
    save(con, "ml", "model_registry", "Model registry", {"data_version": ver, "mlflow_tracking": str(ROOT / "mlruns"), "models_dir": str(MODELS),
         "artifacts": sorted(p.name for p in MODELS.glob("*.joblib")), "summary": out, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}, "Which models exist and how were they validated?")
    return out
