"""Section 6 - machine-learning visualizations. Every chart reads artifacts stored by backend/analytics/ml.py (real model outputs)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import Ctx, Unavailable, analytics, chart, need_rows, payload, series_defs, table_from

S = 6
MODEL_NAMES = {"logistic_regression": "Logistic regression", "random_forest": "Random forest", "xgboost": "XGBoost"}
MODEL_COLORS = {"Logistic regression": "#8E6BBF", "Random forest": "#009F3D", "XGBoost": "#0085C7"}
CLUSTER_COLORS = ["#0085C7", "#F4A300", "#009F3D", "#DF0024", "#8E6BBF", "#FF8A3D", "#2BB3B1", "#B0B7C3"]


def _med():
    return analytics("ml", "medal_prediction")


def _ath():
    return analytics("ml", "athlete_medal_model")


def _clu():
    return analytics("ml", "clustering")


def _need(p, key, what):
    if key not in p:
        raise Unavailable(f"{what} was not stored - re-run scripts/run_analytics.py --only ml")
    return p[key]


@chart("ml_actual_pred", S, "machine-learning", "Actual versus predicted medals", "scatter", "Medal prediction backtest", "analytics_results(ml/medal_prediction)",
       "Judge how close out-of-sample predictions are to reality", (), ("table",))
def actual_pred(ctx: Ctx):
    p = _med()
    s = pd.DataFrame(p["actual_vs_predicted_sample"])
    need_rows(s, "predictions")
    m = p["metrics_all_participating_nocs"][p["best_model_by_rmse"]]
    rows = [{"x": float(r.pred_best), "y": float(r.total), "name": f"{r.noc_code} {r.games_id.replace('_', ' ')}", "group": r.games_id.split("_")[1].capitalize(), "noc": r.noc_code} for r in s.itertuples()]
    return payload("ml_actual_pred", "scatter", {"rows": rows, "xLabel": f"Predicted medals ({p['best_model_by_rmse'].replace('_', ' ')})", "yLabel": "Actual medals", "diag": {"label": "perfect prediction", "slope": 1}, "groupLabel": "Season",
                   "noSize": True, "colors": {"Summer": "#F4A300", "Winter": "#0085C7"}}, axes={"x": "Predicted", "y": "Actual"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation=f"{len(rows)} randomly sampled held-out NOC-Games predictions (out of {p['design']['n_predictions']:,}); each Games is predicted using only earlier Games. Best model by RMSE: {p['best_model_by_rmse'].replace('_', ' ')} "
                                  f"(MAE {m['mae']:.2f}, RMSE {m['rmse']:.2f}, R2 {m['r2']:.2f}). Points on the dashed diagonal are exact. {p['caveat']}")


@chart("ml_pred_interval", S, "machine-learning", "Prediction intervals for one Games", "interval", "Medal prediction backtest", "analytics_results(ml/medal_prediction)",
       "Show predicted medals with an 80% interval against the actual result", ("games_id", "top"), ())
def pred_interval(ctx: Ctx):
    p = _med()
    t = pd.DataFrame(p["actual_vs_predicted_top"])
    need_rows(t, "predictions")
    gid = ctx.games_id if ctx.games_id in set(t.games_id) else t.games_id.iloc[0]
    g = t[t.games_id == gid].sort_values("total", ascending=False).head(ctx.top or 15)
    pi = p["prediction_interval_80"]
    rows = [{"name": r.noc_code, "pred": float(r.pred_best), "lo": float(r.pi_low), "hi": float(r.pi_high), "actual": float(r.total), "inside": bool(r.pi_low <= r.total <= r.pi_high)} for r in g.itertuples()]
    inside = sum(r["inside"] for r in rows)
    return payload("ml_pred_interval", "interval", {"rows": rows, "xLabel": "Medals", "predLabel": "Predicted", "intervalLabel": "80% prediction interval", "actualLabel": "Actual"}, axes={"x": "Medals", "y": "NOC"}, ctx=ctx,
                   table=table_from(rows), drill={"type": "country", "key": "name"},
                   interpretation=f"{gid.replace('_', ' ')}: the actual result lies inside the interval for {inside} of {len(rows)} shown nations. Across all backtests the nominal 80% interval covers {100 * pi['empirical_coverage']:.0f}% of results "
                                  f"(mean width {pi['mean_width']:.1f} medals). {pi['note']}. The interval comes from a separate quantile model, so the point prediction can fall outside it.",
                   notes=["The nations shown are the largest results available in the stored top-60 set; choose the Games with the games_id filter."])


@chart("ml_residual_dist", S, "machine-learning", "Distribution of prediction residuals", "xy", "Medal prediction backtest", "analytics_results(ml/medal_prediction)",
       "Check whether prediction errors are centred and symmetric", (), ("area",))
def residual_dist(ctx: Ctx):
    p = _med()
    s = pd.DataFrame(p["actual_vs_predicted_sample"])
    need_rows(s, "predictions")
    r = (s.total - s.pred_best).values
    lo, hi = np.percentile(r, [1, 99])
    counts, edges = np.histogram(np.clip(r, lo, hi), bins=30)
    rows = [{"bin": round(float((edges[i] + edges[i + 1]) / 2), 2), "NOC-Games": int(c)} for i, c in enumerate(counts)]
    return payload("ml_residual_dist", "xy", {"x": "bin", "xType": "number", "rows": rows, "series": [{"key": "NOC-Games", "color": "#0085C7"}], "variant": "bar", "barGap": 0, "xLabel": "Residual = actual - predicted (medals)",
                   "yLabel": "NOC-Games", "refs": [{"x": 0, "label": "no error"}]}, axes={"x": "Residual (medals)", "y": "Count"}, ctx=ctx,
                   interpretation=f"Mean residual {r.mean():+.2f}, median {np.median(r):+.2f}, SD {r.std():.2f} (n = {len(r)}; the 1% most extreme values are clipped into the end bins). A centred, symmetric bell means no systematic over- or under-prediction; a heavy right tail means a few nations beat the forecast by a lot.")


@chart("ml_feature_importance", S, "machine-learning", "Feature importance: country medal model", "xy", "Medal prediction backtest", "analytics_results(ml/medal_prediction)",
       "Show which inputs drive country medal predictions", (), ("table",))
def feature_importance_country(ctx: Ctx):
    p = _med()["interpretability"]
    pi = pd.DataFrame(_need(p, "permutation_importance_rf", "permutation importance")).sort_values("importance_mae")
    rows = [{"name": r.feature, "Increase in MAE when shuffled": round(float(r.importance_mae), 3), "sd": round(float(r.std), 3)} for r in pi.itertuples()]
    return payload("ml_feature_importance", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "Increase in MAE when shuffled", "color": "#009F3D"}], "variant": "bar", "horizontal": True,
                   "yLabel": "Increase in mean absolute error (medals) when the feature is shuffled"}, axes={"x": "MAE increase", "y": "Feature"}, ctx=ctx,
                   interpretation="Permutation importance of the random-forest model on held-out Games: how much the error grows when one input is randomly shuffled (larger = the model relies on it more). Correlated inputs share importance, so this is not a causal ranking.")


@chart("ml_feature_importance_athlete", S, "machine-learning", "Feature importance: athlete medal model", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Show which inputs drive an athlete's medal probability", (), ("table",))
def feature_importance_athlete(ctx: Ctx):
    a = _ath()
    pi = pd.DataFrame(a["interpretability"]["permutation_importance_best"]).sort_values("importance_pr_auc")
    rows = [{"name": r.feature, "Drop in PR-AUC when shuffled": round(float(r.importance_pr_auc), 4)} for r in pi.itertuples()]
    return payload("ml_feature_importance_athlete", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "Drop in PR-AUC when shuffled", "color": "#0085C7"}], "variant": "bar", "horizontal": True,
                   "yLabel": f"Drop in PR-AUC when shuffled ({a['best_model_by_pr_auc'].replace('_', ' ')})"}, axes={"x": "PR-AUC drop", "y": "Feature"}, ctx=ctx,
                   interpretation="Permutation importance on the test period (2008-2026): how much the precision-recall AUC falls when a feature is shuffled. Prior medal success of the NOC and of the sport carry most of the signal, i.e. the model mostly reflects established strength rather than athlete-specific traits.")


@chart("ml_shap_bar", S, "machine-learning", "Mean absolute SHAP value per feature", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Rank features by their average impact on the XGBoost prediction", (), ("table",))
def shap_bar(ctx: Ctx):
    sh = _ath()["interpretability"].get("shap_mean_abs_xgboost")
    if not sh:
        raise Unavailable("SHAP values were not stored")
    rows = [{"name": k, "mean |SHAP| (log-odds)": round(float(v), 4)} for k, v in sorted(sh.items(), key=lambda kv: kv[1])]
    return payload("ml_shap_bar", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "mean |SHAP| (log-odds)", "color": "#D4AF37"}], "variant": "bar", "horizontal": True,
                   "yLabel": "Mean absolute SHAP value (change in log-odds of a medal)"}, axes={"x": "mean |SHAP|", "y": "Feature"}, ctx=ctx,
                   interpretation="Average magnitude of each feature's contribution to the XGBoost medal probability, computed with TreeSHAP on 4,000 test participations. Unlike permutation importance, this measures contribution to individual predictions.")


@chart("ml_shap_summary", S, "machine-learning", "SHAP summary (beeswarm)", "beeswarm", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Show how feature values push individual predictions up or down", (), ())
def shap_summary(ctx: Ctx):
    sh = _need(_ath()["interpretability"], "shap_sample_xgboost", "the SHAP sample")
    feats = sh["features"]
    V, SV = np.asarray(sh["values"], float), np.asarray(sh["shap"], float)
    order = np.argsort(-np.abs(SV).mean(0))
    rng = np.random.default_rng(11)
    pts = []
    for lane, j in enumerate(order):
        lo, hi = np.percentile(V[:, j], [5, 95])
        norm = np.clip((V[:, j] - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros(len(V))
        idx = rng.choice(len(V), min(450, len(V)), replace=False)
        pts += [{"lane": lane, "shap": round(float(SV[i, j]), 4), "v": round(float(norm[i]), 3), "raw": round(float(V[i, j]), 3), "jit": round(float(rng.uniform(-.32, .32)), 3)} for i in idx]
    return payload("ml_shap_summary", "beeswarm", {"features": [feats[j] for j in order], "points": pts, "xLabel": "SHAP value (impact on log-odds of a medal)", "colorLow": "low feature value", "colorHigh": "high feature value"},
                   axes={"x": "SHAP value", "y": "Feature"}, ctx=ctx, table=table_from([{"feature": feats[order[p["lane"]]], "shap": p["shap"], "feature_value": p["raw"]} for p in pts[:3000]]),
                   interpretation="Each dot is one test-period participation (450 random per feature). Position = push on the medal probability; colour = the feature's value (blue low, red high, scaled to the 5th-95th percentile). "
                                  "Red dots to the right of centre mean 'higher value raises the medal chance'. SHAP describes the model, not causal effects.")


@chart("ml_shap_dependence", S, "machine-learning", "SHAP dependence plot", "scatter", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Show how one feature's value changes its effect on the prediction", ("metric",), ("table",))
def shap_dependence(ctx: Ctx):
    sh = _need(_ath()["interpretability"], "shap_sample_xgboost", "the SHAP sample")
    feats = sh["features"]
    V, SV = np.asarray(sh["values"], float), np.asarray(sh["shap"], float)
    order = np.argsort(-np.abs(SV).mean(0))
    f = ctx.metric if ctx.metric in feats else feats[order[0]]
    j = feats.index(f)
    rows = [{"x": float(V[i, j]), "y": float(SV[i, j])} for i in range(len(V))]
    return payload("ml_shap_dependence", "scatter", {"rows": rows, "xLabel": f"Value of {f}", "yLabel": f"SHAP value of {f} (log-odds)", "refY": 0, "noSize": True, "groupLabel": None}, axes={"x": f, "y": "SHAP"}, ctx=ctx,
                   interpretation=f"How {f} moves the predicted medal chance (1,500 test participations). The vertical spread at one x value comes from interactions with other features. Choose another feature with the metric filter: {', '.join(feats)}.")


@chart("ml_roc", S, "machine-learning", "ROC curves", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Compare models' ability to rank medalists above non-medalists", (), ("table",))
def roc(ctx: Ctx):
    a = _ath()
    cv = _need(a, "curves", "ROC curves")
    series, rows_by_x = [], {}
    pts = []
    for k, c in cv.items():
        nm = MODEL_NAMES.get(k, k); auc = a["models"][k]["roc_auc"]
        series.append({"key": f"{nm} (AUC {auc:.3f})", "color": MODEL_COLORS.get(nm)})
        for x, y in zip(c["roc"]["fpr"], c["roc"]["tpr"]):
            pts.append({"fpr": round(float(x), 4), "k": f"{nm} (AUC {auc:.3f})", "tpr": round(float(y), 4)})
    p = pd.DataFrame(pts)
    rows = []
    for key, g in p.groupby("k"):
        for r in g.itertuples():
            rows.append({"fpr": r.fpr, key: r.tpr})
    return payload("ml_roc", "xy", {"x": "fpr", "xType": "number", "rows": rows, "series": series, "variant": "line", "xLabel": "False positive rate", "yLabel": "True positive rate (recall)", "diag": True, "xDomain": [0, 1], "yDomain": [0, 1], "curve": "linear",
                   "sparse": True}, axes={"x": "False positive rate", "y": "True positive rate"}, ctx=ctx,
                   interpretation="Test period 2008-2026 (never used for training or threshold choice). The diagonal is a coin flip (AUC 0.5); curves nearer the top-left are better. ROC can look optimistic when medalists are rare (base rate "
                                  f"{100 * a['design']['base_rate_test']:.0f}%), so read it together with the precision-recall curve.")


@chart("ml_pr", S, "machine-learning", "Precision-recall curves", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Compare models when positives (medalists) are rare", (), ("table",))
def pr(ctx: Ctx):
    a = _ath()
    cv = _need(a, "curves", "precision-recall curves")
    series, rows = [], []
    for k, c in cv.items():
        nm = MODEL_NAMES.get(k, k); ap = a["models"][k]["pr_auc"]; key = f"{nm} (PR-AUC {ap:.3f})"
        series.append({"key": key, "color": MODEL_COLORS.get(nm)})
        rows += [{"recall": round(float(r), 4), key: round(float(p), 4)} for r, p in zip(c["pr"]["recall"], c["pr"]["precision"])]
    base = a["design"]["base_rate_test"]
    return payload("ml_pr", "xy", {"x": "recall", "xType": "number", "rows": rows, "series": series, "variant": "line", "xLabel": "Recall", "yLabel": "Precision", "refs": [{"y": base, "label": f"base rate {base:.2f}"}], "xDomain": [0, 1], "yDomain": [0, 1], "sparse": True},
                   axes={"x": "Recall", "y": "Precision"}, ctx=ctx,
                   interpretation=f"Precision against recall on the 2008-2026 test set. The dashed line is the precision of guessing 'medal' for everyone ({100 * base:.0f}%). The curves sit well above it, but precision drops quickly as recall rises: many medalists cannot be identified in advance.")


@chart("ml_confusion", S, "machine-learning", "Confusion matrix", "heatmap", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Show correct and incorrect classifications at the chosen decision threshold", ("metric",), ("table",))
def confusion(ctx: Ctx):
    a = _ath()
    k = ctx.metric if ctx.metric in a["models"] else a["best_model_by_pr_auc"]
    m = a["models"][k]; cm = m["confusion_matrix"]
    tot = {"Actual: no medal": cm["tn"] + cm["fp"], "Actual: medal": cm["fn"] + cm["tp"]}
    cells = [("Actual: no medal", "Predicted: no medal", cm["tn"]), ("Actual: no medal", "Predicted: medal", cm["fp"]), ("Actual: medal", "Predicted: no medal", cm["fn"]), ("Actual: medal", "Predicted: medal", cm["tp"])]
    rows = [{"r": r, "c": c, "v": int(v), "pct": round(100 * v / tot[r], 1), "label": f"{r} / {c}: {int(v):,} ({100 * v / tot[r]:.1f}% of {r.lower()})"} for r, c, v in cells]
    return payload("ml_confusion", "heatmap", {"rows": rows, "rowOrder": ["Actual: no medal", "Actual: medal"], "colOrder": ["Predicted: no medal", "Predicted: medal"], "scale": "seq", "vLabel": "Participations", "format": "int", "cell": "number", "showPct": True},
                   axes={"x": "Predicted", "y": "Actual"}, ctx=ctx, table=table_from([{"actual": r["r"], "predicted": r["c"], "count": r["v"], "pct_of_actual_row": r["pct"]} for r in rows]),
                   interpretation=f"{MODEL_NAMES.get(k, k)} at the decision threshold {m['threshold_from_validation']:.2f} chosen on the 2000-2007 validation set (test = 2008-2026). Precision {m['precision']:.2f}, recall {m['recall']:.2f}, F1 {m['f1']:.2f}. "
                                  "Percentages are shares of each actual class. Choose a model with the metric filter: " + ", ".join(a["models"]))


@chart("ml_calibration", S, "machine-learning", "Calibration curves", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Check whether predicted probabilities match observed frequencies", (), ("table",))
def calibration(ctx: Ctx):
    a = _ath()
    series, rows = [], []
    for k, m in a["models"].items():
        nm = MODEL_NAMES.get(k, k); key = f"{nm} (Brier {m['brier']:.3f})"
        series.append({"key": key, "color": MODEL_COLORS.get(nm)})
        rows += [{"predicted": round(float(c["mean_predicted"]), 4), key: round(float(c["observed_rate"]), 4), "n": int(c["n"])} for c in m["calibration"]]
    need_rows(rows, "calibration bins")
    return payload("ml_calibration", "xy", {"x": "predicted", "xType": "number", "rows": rows, "series": series, "variant": "line", "dot": True, "xLabel": "Mean predicted probability (decile bin)", "yLabel": "Observed medal rate", "diag": True,
                   "xDomain": [0, 1], "yDomain": [0, 1], "sparse": True}, axes={"x": "Predicted probability", "y": "Observed frequency"}, ctx=ctx,
                   interpretation="Participations are grouped into probability bins; a perfectly calibrated model lies on the diagonal. Curves below it over-predict. Brier score (lower is better) summarises probability accuracy. "
                                  "The random forest is trained with class weights, which usually inflates its probabilities.")


@chart("ml_learning_curve", S, "machine-learning", "Learning curve", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Diagnose whether more training data would help", (), ("table",))
def learning_curve(ctx: Ctx):
    lc = _need(_ath(), "learning_curve", "the learning curve")
    rows = [{"n_train": int(r["n_train"]), "Training PR-AUC": round(r["train_pr_auc"], 4), "Validation PR-AUC": round(r["validation_pr_auc"], 4)} for r in lc]
    gap = rows[-1]["Training PR-AUC"] - rows[-1]["Validation PR-AUC"]
    return payload("ml_learning_curve", "xy", {"x": "n_train", "xType": "number", "rows": rows, "series": [{"key": "Training PR-AUC", "color": "#9AA3AF"}, {"key": "Validation PR-AUC", "color": "#0085C7"}], "variant": "line", "dot": True,
                   "xLabel": "Training participations", "yLabel": "PR-AUC (XGBoost)"}, axes={"x": "Training set size", "y": "PR-AUC"}, ctx=ctx,
                   interpretation=f"XGBoost trained on growing random subsets of the pre-2000 data and scored on the 2000-2007 validation Games. Validation PR-AUC levels off near {rows[-1]['Validation PR-AUC']:.2f} while training PR-AUC stays {gap:.2f} higher: "
                                  "more data of the same kind is unlikely to help much; better features or a different problem framing would.")


@chart("ml_cv_compare", S, "machine-learning", "Cross-validation comparison across time folds", "xy", "Athlete medal model", "analytics_results(ml/athlete_medal_model)",
       "Compare models' stability over successive periods", ("metric",), ("table",))
def cv_compare(ctx: Ctx):
    cv = pd.DataFrame(_need(_ath(), "cross_validation", "the cross-validation results"))
    need_rows(cv, "folds")
    met = ctx.metric if ctx.metric in ("roc_auc", "pr_auc") else "pr_auc"
    cv["m"] = cv.model.map(lambda k: MODEL_NAMES.get(k, k))
    pv = cv.pivot_table(index="fold", columns="m", values=met).reset_index()
    base = cv.drop_duplicates("fold").set_index("fold").base_rate
    rows = pv.to_dict("records")
    for r in rows:
        r["base rate"] = float(base[r["fold"]]) if met == "pr_auc" else None
    keys = [c for c in pv.columns if c != "fold"]
    ser = series_defs(keys, colors=MODEL_COLORS) + ([{"key": "base rate", "color": "#B0B7C3"}] if met == "pr_auc" else [])
    return payload("ml_cv_compare", "xy", {"x": "fold", "xType": "category", "rows": rows, "series": ser, "variant": "grouped", "xLabel": "Test period (each fold trains only on earlier Games)", "yLabel": "PR-AUC" if met == "pr_auc" else "ROC-AUC"},
                   axes={"x": "Fold", "y": met.replace("_", "-").upper()}, ctx=ctx, table=table_from(cv.drop(columns="m")),
                   interpretation="Expanding-window, chronological cross-validation: each fold is scored on later Games than it was trained on, so the comparison reflects forecasting, not interpolation. "
                                  "Models track each other closely, and performance is stable across eras. PR-AUC bars include the base-rate (random) level. Switch the metric with metric=roc_auc.")


@chart("ml_kmeans", S, "machine-learning", "K-means clusters of nations", "scatter", "ML clustering", "analytics_results(ml/clustering)",
       "Show the groups of nations with similar Olympic profiles", (), ("table",))
def kmeans(ctx: Ctx):
    c = _clu()
    pts = pd.DataFrame(c["points"])
    rows = [{"x": float(r.appearances), "y": float(r.total_medals) + 1, "name": r.historical_name, "noc": r.noc_code, "group": f"Cluster {int(r.cluster) + 1}", "medals": int(r.total_medals)} for r in pts.itertuples()]
    prof = {int(p["cluster"]): p for p in c["cluster_profiles"]}
    return payload("ml_kmeans", "scatter", {"rows": rows, "xLabel": "Games attended", "yLabel": "Total medals + 1 (log scale)", "logY": True, "groupLabel": "K-means cluster", "noSize": True, "extra": ["medals"]},
                   axes={"x": "Games attended", "y": "Medals (log)"}, ctx=ctx, drill={"type": "country", "key": "noc"}, table=table_from([{"cluster": f"Cluster {k + 1}", "n_nocs": p["n_nocs"], "mean_total_medals": p["total_medals"], "examples": ", ".join(p["examples"]), "distinguishing": "; ".join(p["distinguishing_features"])} for k, p in sorted(prof.items())]),
                   interpretation=f"K-means with k = {c['chosen_k']} (silhouette {c['kmeans_silhouette']:.2f}) on {len(c['features'])} standardised features for {c['n_nocs']} NOCs with at least 3 Games. Clusters were fit on all features; this view shows two of them "
                                  "(attendance and total medals). The table gives each cluster's most distinguishing features. Clusters are descriptive groupings, not categories with natural boundaries.")


@chart("ml_pca2d", S, "machine-learning", "PCA projection (2D)", "scatter", "ML clustering", "analytics_results(ml/clustering)",
       "Reveal structure in the 8-dimensional country profile", (), ("table",))
def pca2d(ctx: Ctx):
    c = _clu()
    ev = c["pca"]["explained_variance_ratio"]
    pts = pd.DataFrame(c["points"])
    rows = [{"x": float(r.pc1), "y": float(r.pc2), "z": float(r.total_medals) + 1, "name": r.historical_name, "noc": r.noc_code, "group": f"Cluster {int(r.cluster) + 1}"} for r in pts.itertuples()]
    load = pd.DataFrame(c["pca"]["loadings"]) if isinstance(c["pca"]["loadings"], list) else pd.DataFrame()
    return payload("ml_pca2d", "scatter", {"rows": rows, "xLabel": f"PC1 ({100 * ev[0]:.0f}% of variance)", "yLabel": f"PC2 ({100 * ev[1]:.0f}% of variance)", "sizeLabel": "Total medals + 1", "groupLabel": "K-means cluster"},
                   axes={"x": "PC1", "y": "PC2"}, ctx=ctx, drill={"type": "country", "key": "noc"}, table=table_from(rows),
                   interpretation=f"Principal components of the standardised features: PC1 and PC2 keep {100 * (ev[0] + ev[1]):.0f}% of the variance. Colour = k-means cluster, size = total medals. "
                                  "Distance between points approximates dissimilarity of Olympic profile; the axes are combinations of features (loadings are stored with the model).")


@chart("ml_pca3d", S, "machine-learning", "PCA projection (3D)", "pca3d", "ML clustering", "analytics_results(ml/clustering)",
       "Show a third principal component that the 2D view hides", (), ("table",))
def pca3d(ctx: Ctx):
    c = _clu()
    ev = c["pca"]["explained_variance_ratio"]
    pts = pd.DataFrame(c["points"])
    if "pc3" not in pts or len(ev) < 3:
        raise Unavailable("3 principal components were not stored - re-run scripts/run_analytics.py --only ml")
    rows = [{"x": float(r.pc1), "y": float(r.pc2), "z": float(r.pc3), "name": r.historical_name, "noc": r.noc_code, "group": f"Cluster {int(r.cluster) + 1}", "size": float(np.log1p(r.total_medals))} for r in pts.itertuples()]
    return payload("ml_pca3d", "pca3d", {"rows": rows, "axes": [f"PC1 ({100 * ev[0]:.0f}%)", f"PC2 ({100 * ev[1]:.0f}%)", f"PC3 ({100 * ev[2]:.0f}%)"]}, axes={}, ctx=ctx, table=table_from(rows), drill={"type": "country", "key": "noc"},
                   interpretation=f"The first three components keep {100 * sum(ev[:3]):.0f}% of the variance. Drag to rotate; points keep their k-means colour. Perspective distorts size, so confirm close points with the table.")


@chart("ml_dendrogram", S, "machine-learning", "Hierarchical clustering dendrogram", "dendrogram", "ML clustering", "analytics_results(ml/clustering)",
       "Show how nations merge into groups as the distance threshold grows", (), ())
def dendrogram(ctx: Ctx):
    c = _clu()
    dg = _need(c, "dendrogram", "the dendrogram")
    return payload("ml_dendrogram", "dendrogram", {"icoord": dg["icoord"], "dcoord": dg["dcoord"], "leaves": dg["leaves"], "yLabel": f"Ward linkage distance ({len(dg['leaves'])} NOCs)"}, axes={}, ctx=ctx,
                   table=table_from([{"leaf_order": i + 1, "noc": n} for i, n in enumerate(dg["leaves"])]),
                   interpretation="Ward agglomerative clustering on the same standardised features. Nations that merge low in the tree are most similar; tall vertical gaps suggest natural cut points. "
                                  f"Agreement with k-means (adjusted Rand index) is {c['hierarchical_vs_kmeans_adjusted_rand']:.2f}.")


@chart("ml_elbow", S, "machine-learning", "Elbow method", "xy", "ML clustering", "analytics_results(ml/clustering)",
       "Judge the number of clusters from the drop in within-cluster variance", (), ("table",))
def elbow(ctx: Ctx):
    c = _clu()
    inertia = _need(c, "inertia_by_k", "within-cluster inertia")
    rows = [{"k": int(k), "Within-cluster sum of squares": round(float(v), 2)} for k, v in sorted(inertia.items(), key=lambda kv: int(kv[0]))]
    return payload("ml_elbow", "xy", {"x": "k", "xType": "number", "rows": rows, "series": [{"key": "Within-cluster sum of squares", "color": "#0085C7"}], "variant": "line", "dot": True, "xLabel": "Number of clusters k",
                   "yLabel": "Within-cluster sum of squares (inertia)", "refs": [{"x": c["chosen_k"], "label": f"chosen k = {c['chosen_k']}"}]}, axes={"x": "k", "y": "Inertia"}, ctx=ctx,
                   interpretation="Inertia always falls as k grows; the 'elbow' is where the gain from another cluster levels off. Here the curve bends gradually with no sharp elbow, so k was chosen with the silhouette criterion instead (next chart).")


@chart("ml_silhouette", S, "machine-learning", "Silhouette score by number of clusters", "xy", "ML clustering", "analytics_results(ml/clustering)",
       "Choose the number of clusters by cluster separation", (), ("table",))
def silhouette(ctx: Ctx):
    c = _clu()
    sil = c["k_selection_silhouette"]
    rows = [{"k": int(k), "Silhouette": round(float(v), 4)} for k, v in sorted(sil.items(), key=lambda kv: int(kv[0]))]
    return payload("ml_silhouette", "xy", {"x": "k", "xType": "category", "rows": rows, "series": [{"key": "Silhouette", "color": "#009F3D"}], "variant": "bar", "xLabel": "Number of clusters k", "yLabel": "Mean silhouette (higher = better separated)",
                   "yDomain": [0, 1]}, axes={"x": "k", "y": "Silhouette"}, ctx=ctx,
                   interpretation=f"k = {c['chosen_k']} has the highest silhouette ({c['kmeans_silhouette']:.2f}), but values for k = 3 to 8 differ by only a few hundredths, and scores below about 0.5 indicate moderate structure: clusters are a useful summary, not sharply separated groups.")


@chart("ml_model_dashboard", S, "machine-learning", "Model comparison dashboard", "scorecard", "ML model registry", "analytics_results(ml/*)",
       "Summarise every model's validated performance in one place", (), ())
def dashboard(ctx: Ctx):
    med, ath, clu = _med(), _ath(), _clu()
    mm = med["metrics_all_participating_nocs"]
    best, naive = med["best_model_by_rmse"], mm["naive_previous_total"]
    pi = med["prediction_interval_80"]
    tiles = [
        {"label": "Medal-count model (best by RMSE)", "value": best.replace("_", " "), "hint": f"RMSE {mm[best]['rmse']:.2f} vs naive {naive['rmse']:.2f} medals ({100 * (1 - mm[best]['rmse'] / naive['rmse']):.0f}% lower)", "status": "ok"},
        {"label": "Prediction interval coverage", "value": f"{100 * pi['empirical_coverage']:.0f}%", "hint": f"nominal {100 * pi['nominal']:.0f}%, mean width {pi['mean_width']:.1f} medals", "status": "ok" if abs(pi["empirical_coverage"] - pi["nominal"]) < 0.1 else "warn"},
        {"label": "Athlete model (best by PR-AUC)", "value": MODEL_NAMES.get(ath["best_model_by_pr_auc"], ath["best_model_by_pr_auc"]), "hint": f"PR-AUC {ath['models'][ath['best_model_by_pr_auc']]['pr_auc']:.2f} vs base rate {ath['design']['base_rate_test']:.2f}", "status": "ok"},
        {"label": "Clustering", "value": f"k = {clu['chosen_k']}", "hint": f"silhouette {clu['kmeans_silhouette']:.2f}; DBSCAN finds {clu['dbscan']['clusters']} dense group(s)", "status": "warn" if clu["kmeans_silhouette"] < 0.5 else "ok"},
    ]
    t1 = [{"model": k.replace("_", " "), "MAE": round(v["mae"], 3), "RMSE": round(v["rmse"], 3), "R2": round(v["r2"], 3)} for k, v in mm.items()]
    t2 = [{"model": MODEL_NAMES.get(k, k), "ROC-AUC": round(v["roc_auc"], 3), "PR-AUC": round(v["pr_auc"], 3), "F1": round(v["f1"], 3), "Precision": round(v["precision"], 3), "Recall": round(v["recall"], 3), "Brier": round(v["brier"], 3)} for k, v in ath["models"].items()]
    return payload("ml_model_dashboard", "scorecard", {"tiles": tiles, "tables": [{"title": "Country medal prediction (held-out Games; medals)", "columns": list(t1[0]), "rows": t1},
                                                                                 {"title": "Athlete medal probability (test 2008-2026)", "columns": list(t2[0]), "rows": t2}]}, axes={}, ctx=ctx,
                   table=table_from([{"family": "country medals", **r} for r in t1] + [{"family": "athlete medal", **r} for r in t2]),
                   interpretation="All figures are chronological backtests: models never see the Games they are scored on. The naive baseline (repeat the previous Games' total) is hard to beat for established nations. "
                                  "Warnings flag intervals that miss their nominal coverage or clusters with a silhouette below 0.5.")
