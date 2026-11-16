import { useParamState } from "../components/navigation/Crumbs";
import { useState } from "react";
import { useApi } from "../lib/api";
import { Async, ChartCard, Note, PageHeader, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, Scatter2 } from "../charts/charts";
import { fmtNum, PALETTE } from "../lib/fmt";

import { MlFindings } from "../components/analytics/KeyFindings";
import { VizSection } from "../viz/VizGallery";
export default function MachineLearningPage() {
  const [tab, setTab] = useParamState("tab", "medal");
  return (
    <div>
      <PageHeader title="Machine learning" subtitle="Every result here is a HISTORICAL BACKTEST with chronological validation (models only ever see editions before the one they predict). Nothing on this page is a forecast of a future Games, and no prediction is guaranteed." />
      <MlFindings />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "medal", label: "Country medal prediction" }, { id: "athlete", label: "Athlete medal probability" }, { id: "cluster", label: "Country clustering" }, { id: "special", label: "Sport specialisation" }, { id: "registry", label: "Model registry" }]} />
      {tab === "medal" && <MedalPrediction />}
      {tab === "athlete" && <AthleteModel />}
      {tab === "cluster" && <Clustering />}
      {tab === "special" && <Specialisation />}
      {tab === "registry" && <Registry />}
      <VizSection page="machine-learning" />
    </div>
  );
}

function MedalPrediction() {
  const q = useApi<any>("/machine-learning/predictions", { kind: "medal_prediction" });
  return (
    <Async q={q}>{({ data, generated_at }) => {
      const m = data.metrics_all_participating_nocs, w = data.metrics_medal_winning_nocs_only;
      const rows = Object.keys(m).map((k) => ({ model: k.replace(/_/g, " "), mae: fmtNum(m[k].mae, 3), rmse: fmtNum(m[k].rmse, 3), r2: fmtNum(m[k].r2, 3), rmse_winners: fmtNum(w[k].rmse, 3) }));
      const imp = data.interpretability;
      return (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Model comparison" subtitle={`${data.design.n_predictions.toLocaleString()} NOC-edition predictions across ${data.design.test_editions.length} test editions; best by RMSE: ${data.best_model_by_rmse}`} height={260}>
            <DataTable height={260} rows={rows} columns={[{ key: "model", width: 190 }, { key: "mae", header: "MAE", align: "right" }, { key: "rmse", header: "RMSE", align: "right" }, { key: "r2", header: "R²", align: "right" }, { key: "rmse_winners", header: "RMSE (medal winners only)", align: "right", width: 170 }]} />
            <p className="mt-2 text-xs text-muted">Baseline "naive previous total" = repeat the NOC's previous total. A model that cannot beat it adds no value; compare rows honestly.</p>
          </ChartCard>
          <ChartCard title="Actual vs predicted" subtitle="Largest 60 medal tallies (best model, with 80% prediction interval from quantile boosting)">
            <Scatter2 data={data.actual_vs_predicted_top} x="total" y="pred_best" name="noc_code" xLabel="Actual medals" yLabel="Predicted medals" colorKey="games_id" />
          </ChartCard>
          <ChartCard title="Error by test edition" subtitle="RMSE of the best model vs the naive baseline"><Bars data={data.per_edition_best_model.map((e: any) => ({ edition: e.games_id, model: e.rmse, naive: e.naive_rmse }))} x="edition" series={[{ key: "model", color: "#0085C7" }, { key: "naive", color: "#B0B7C3" }]} /></ChartCard>
          <ChartCard title="Prediction intervals" subtitle={`Nominal 80%; empirical coverage ${fmtNum(100 * data.prediction_interval_80.empirical_coverage, 1)}%, mean width ${fmtNum(data.prediction_interval_80.mean_width, 1)} medals`} height={120}><p className="text-sm text-muted">{data.prediction_interval_80.note}</p></ChartCard>
          <ChartCard title="Permutation importance (random forest, test editions)" subtitle="Increase in MAE when a feature is shuffled"><Bars horizontal data={imp.permutation_importance_rf.map((r: any) => ({ name: r.feature, importance: r.importance_mae }))} x="name" series={[{ key: "importance", color: "#F4C300" }]} /></ChartCard>
          <ChartCard title="SHAP: mean |contribution| (XGBoost)" subtitle="Average effect size of each feature on predicted medals">{imp.shap_mean_abs_xgboost ? <Bars horizontal data={Object.entries<number>(imp.shap_mean_abs_xgboost).map(([name, v]) => ({ name, shap: v })).sort((a, b) => b.shap - a.shap)} x="name" series={[{ key: "shap", color: "#009F3D" }]} /> : <Note>{imp.shap_error}</Note>}</ChartCard>
          {Object.entries<any>(imp.partial_dependence_rf).map(([k, v], i) => <ChartCard key={k} title={`Partial dependence: ${k}`} subtitle="Average prediction as one feature varies (random forest)"><LineSeries data={v.x.map((x: number, j: number) => ({ x, y: v.y[j] }))} x="x" series={[{ key: "y", name: "predicted medals", color: PALETTE[i] }]} /></ChartCard>)}
          <div className="xl:col-span-2"><Note tone="warn"><b>Design.</b> {data.design.split} Target: {data.design.target}. <b>Entry-list-time features</b> ({data.design.entry_list_time_features.join(", ")}) describe the delegation entered for the edition being predicted. <b>Backtest only:</b> {data.design.what_this_is} {data.caveat} Version {data.model_version}, generated {generated_at?.slice(0, 10)}.</Note></div>
        </div>);
    }}</Async>
  );
}

function AthleteModel() {
  const q = useApi<any>("/machine-learning/predictions", { kind: "athlete_medal_model" });
  const [m, setM] = useState("xgboost");
  return (
    <Async q={q}>{({ data }) => {
      const mm = data.models[m];
      const cm = mm.confusion_matrix;
      return (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Model comparison (test: 2008–2026)" subtitle={`Base rate of medal participations in test ${fmtNum(100 * data.design.base_rate_test, 1)}%; best by PR-AUC: ${data.best_model_by_pr_auc}`} height={220}>
            <DataTable rows={Object.entries<any>(data.models).map(([k, v]) => ({ model: k.replace(/_/g, " "), precision: fmtNum(v.precision, 3), recall: fmtNum(v.recall, 3), f1: fmtNum(v.f1, 3), roc_auc: fmtNum(v.roc_auc, 3), pr_auc: fmtNum(v.pr_auc, 3), brier: fmtNum(v.brier, 3), threshold: fmtNum(v.threshold_from_validation, 2) }))}
              columns={[{ key: "model", width: 170 }, ...["precision", "recall", "f1", "roc_auc", "pr_auc", "brier", "threshold"].map((k) => ({ key: k, header: k.replace("_", "-"), align: "right" as const, width: 90 }))]} height={200} />
          </ChartCard>
          <ChartCard title="Confusion matrix" subtitle={`${m.replace("_", " ")} at the validation-chosen threshold`} right={<select aria-label="Model" className="input" value={m} onChange={(e) => setM(e.target.value)}>{Object.keys(data.models).map((k) => <option key={k}>{k}</option>)}</select>}>
            <div className="grid max-w-md grid-cols-2 gap-2 text-center">
              {[["True negative", cm.tn, "bg-surface2"], ["False positive", cm.fp, "bg-red/20"], ["False negative", cm.fn, "bg-yellow/20"], ["True positive", cm.tp, "bg-green/25"]].map(([l, v, c]: any) => <div key={l} className={`rounded-lg p-4 ${c}`}><div className="text-[11px] uppercase tracking-wider text-muted">{l}</div><div className="font-display text-3xl tabnum">{v.toLocaleString()}</div></div>)}
            </div>
          </ChartCard>
          <ChartCard title="Calibration (reliability)" subtitle="Points on the diagonal = predicted probabilities match observed rates"><Scatter2 data={mm.calibration} x="mean_predicted" y="observed_rate" z="n" xLabel="Mean predicted probability" yLabel="Observed medal rate" /></ChartCard>
          <ChartCard title="Permutation importance (best model, PR-AUC)"><Bars horizontal data={data.interpretability.permutation_importance_best.map((r: any) => ({ name: r.feature, importance: r.importance_pr_auc }))} x="name" series={[{ key: "importance", color: "#F4C300" }]} /></ChartCard>
          <ChartCard title="SHAP mean |value| (XGBoost, 4,000 test rows)">{data.interpretability.shap_mean_abs_xgboost ? <Bars horizontal data={Object.entries<number>(data.interpretability.shap_mean_abs_xgboost).map(([name, v]) => ({ name, shap: v })).sort((a, b) => b.shap - a.shap)} x="name" series={[{ key: "shap", color: "#009F3D" }]} /> : <Note>{data.interpretability.shap_error}</Note>}</ChartCard>
          <ChartCard title="Selection bias & data limits" height={160}><ul className="list-disc space-y-1 pl-5 text-sm text-muted">{data.bias_notes.map((b: string) => <li key={b}>{b}</li>)}</ul></ChartCard>
          <div className="xl:col-span-2"><Note>{data.design.leakage_controls} Train: {data.design.train}; validation: {data.design.validation}; test: {data.design.test}.</Note></div>
        </div>);
    }}</Async>
  );
}

function Clustering() {
  const q = useApi<any>("/machine-learning/predictions", { kind: "clustering" });
  return (
    <Async q={q}>{({ data }) => (
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Countries in PCA space" subtitle={`K-Means k = ${data.chosen_k} (silhouette ${fmtNum(data.kmeans_silhouette, 3)}); PC1+PC2 explain ${fmtNum(100 * (data.pca.explained_variance_ratio[0] + data.pca.explained_variance_ratio[1]), 1)}% of variance`} height={420}>
          <Scatter2 height={420} data={data.points} x="pc1" y="pc2" z="total_medals" name="historical_name" colorKey="cluster" xLabel="PC1" yLabel="PC2" />
        </ChartCard>
        <ChartCard title="Choosing k" subtitle="Silhouette score by k (k = 2 is excluded: it only separates medal volume)"><Bars data={Object.entries<number>(data.k_selection_silhouette).map(([k, v]) => ({ k, silhouette: v }))} x="k" series={[{ key: "silhouette", color: "#0085C7" }]} /></ChartCard>
        <ChartCard title="Cluster profiles" subtitle="Feature means; examples are the cluster's top medal-winning NOCs. No subjective names are assigned." height={300}>
          <DataTable height={320} rows={data.cluster_profiles.map((p: any) => ({ cluster: p.cluster, n: p.n_nocs, examples: (p.examples || []).join(", "), distinguishing: (p.distinguishing_features || []).join("; "), total_medals: fmtNum(p.total_medals, 0), winter_share: fmtNum(p.winter_share, 2), gold_ratio: fmtNum(p.gold_ratio, 2), hhi: fmtNum(p.sport_hhi, 2) }))}
            columns={[{ key: "cluster", width: 70 }, { key: "n", align: "right", width: 50 }, { key: "examples", width: 200 }, { key: "distinguishing", header: "Most distinguishing features", width: 380 }, { key: "total_medals", header: "Avg medals", align: "right", width: 100 }, { key: "winter_share", align: "right", width: 100 }, { key: "gold_ratio", align: "right", width: 90 }, { key: "hhi", header: "Sport HHI", align: "right", width: 90 }]} />
        </ChartCard>
        <ChartCard title="Method cross-checks" height={160}><ul className="space-y-1 text-sm text-muted"><li>Hierarchical (Ward) vs K-Means agreement: adjusted Rand index {fmtNum(data.hierarchical_vs_kmeans_adjusted_rand, 3)}.</li><li>DBSCAN (eps {fmtNum(data.dbscan.eps, 2)}): {data.dbscan.clusters} dense groups, {data.dbscan.noise_points} noise points. {data.dbscan.justification}</li><li>Features: {data.features.join(", ")}. Inclusion: {data.inclusion_rule}.</li></ul></ChartCard>
      </div>)}</Async>
  );
}

function Specialisation() {
  const q = useApi<any>("/machine-learning/predictions", { kind: "sport_specialization" });
  return (
    <Async q={q}>{({ data }) => (
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Most specialised NOCs" subtitle={data.definition} height={520}>
          <DataTable height={500} rows={data.countries} exportName="specialisation" columns={[{ key: "historical_name", header: "NOC", width: 180 }, { key: "dominant_sport", width: 170 }, { key: "dominant_sport_share", header: "Share", align: "right", width: 80, render: (r) => `${fmtNum(100 * r.dominant_sport_share, 0)}%` }, { key: "sport_hhi", header: "HHI", align: "right", width: 70, render: (r) => fmtNum(r.sport_hhi, 2) }, { key: "winter_share", header: "Winter", align: "right", width: 80, render: (r) => `${fmtNum(100 * r.winter_share, 0)}%` }, { key: "total_medals", header: "Medals", align: "right", width: 80 }, { key: "profile", width: 180 }]} />
        </ChartCard>
        <ChartCard title="Country dominance by sport" subtitle="NOC's share of all medals awarded in a sport (≥ 15%, ≥ 5 medals)" height={520}>
          <DataTable height={500} rows={data.dominant_country_sport_pairs} columns={[{ key: "sport_name", header: "Sport", width: 180 }, { key: "noc_code", header: "NOC", width: 70 }, { key: "m", header: "Medals", align: "right", width: 80 }, { key: "share", align: "right", width: 90, render: (r) => `${fmtNum(100 * r.share, 0)}%` }]} />
        </ChartCard>
      </div>)}</Async>
  );
}

function Registry() {
  const q = useApi<any>("/machine-learning/models");
  return (
    <Async q={q}>{(d) => (
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Registry" height={200}><ul className="space-y-1 text-sm"><li>Data version: <code>{d.registry.data_version}</code></li><li>MLflow tracking store: <code className="break-all">{d.registry.mlflow_tracking}</code> (run <code>mlflow ui</code>)</li><li>Validation: {d.validation}</li></ul></ChartCard>
        <ChartCard title="Saved model artefacts" height={200}><ul className="space-y-1 text-sm">{d.registry.artifacts.map((a: string) => <li key={a}><code>{a}</code></li>)}</ul></ChartCard>
      </div>)}</Async>
  );
}
