import { useParamState } from "../components/navigation/Crumbs";
import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useApi } from "../lib/api";
import { Async, ChartCard, Kpi, Note, PageHeader, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, Heat } from "../charts/charts";
import { fmtInt } from "../lib/fmt";

import { VizSection } from "../viz/VizGallery";
export default function EngineeringPage() {
  const [tab, setTab] = useParamState("tab", "pipeline");
  const ps = useApi<any>("/data-engineering/pipeline-status");
  const dq = useApi<any>("/data-quality");
  return (
    <div>
      <PageHeader title="Data engineering monitor" subtitle="Live pipeline state straight from the warehouse: Bronze → Silver → Gold layers, validation results, completeness and reconciliation." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "pipeline", label: "Pipeline & layers" }, { id: "validation", label: "Validation" }, { id: "completeness", label: "Completeness" }, { id: "reconciliation", label: "Medal reconciliation" }, { id: "findings", label: "Audit findings" }]} />
      {tab === "pipeline" && (
        <Async q={ps}>{(d) => (
          <div>
            <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <Kpi label="Bronze tables" value={d.layers.bronze_tables} hint="raw / source, never modified" accent="#CD7F32" /><Kpi label="Silver tables" value={d.layers.silver_tables} hint="cleaned, de-duplicated" accent="#C0C7D1" /><Kpi label="Gold marts" value={d.layers.gold_tables} hint="analytical marts" accent="#D4AF37" />
              <Kpi label="Participations (silver)" value={d.row_counts.silver_participations} /><Kpi label="Athletes (career mart)" value={d.row_counts.gold_athlete_career} accent="#009F3D" /><Kpi label="Podium results (gold)" value={d.row_counts.gold_event_results} accent="#0085C7" />
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Row counts across layers"><Bars horizontal data={Object.entries<number>(d.row_counts).map(([name, v]) => ({ name, rows: v }))} x="name" series={[{ key: "rows", color: "#0085C7" }]} yFormat={(v) => fmtInt(v)} /></ChartCard>
              <ChartCard title="Pipeline runs" subtitle="Each run of the medallion build is recorded" height={280}>
                <DataTable rows={d.runs} height={300} columns={[{ key: "run_id", width: 60 }, { key: "stage", width: 100 }, { key: "status", width: 90 }, { key: "started_at", width: 220 }, { key: "finished_at", width: 220 }]} empty="No recorded runs yet." />
              </ChartCard>
              <ChartCard title="Analytics outputs" height={200}><DataTable rows={d.analytics_generated} columns={[{ key: "module" }, { key: "results", align: "right" }, { key: "last", header: "Generated", width: 240 }]} /></ChartCard>
              <ChartCard title="Incremental build state" height={200}><div className="text-sm">Gold marts are rebuilt per Games only when that Games' source fingerprint changes. Games tracked: <b>{d.gold_build_state[0]?.games}</b>; last built <b>{d.gold_build_state[0]?.last_built}</b>.</div></ChartCard>
            </div>
          </div>)}</Async>)}
      {tab === "validation" && (
        <Async q={dq}>{(d) => { const ok = d.validation.filter((v: any) => v.passed === "True").length; return (
          <ChartCard title={`Expectation checks: ${ok} / ${d.validation.length} passed`} subtitle="Failing checks are findings, never hidden" height={520}>
            <DataTable rows={d.validation} height={500} columns={[{ key: "passed", header: "", width: 40, render: (r) => r.passed === "True" ? <CheckCircle2 className="h-4 w-4 text-green" aria-label="passed" /> : <XCircle className="h-4 w-4 text-red" aria-label="failed" /> }, { key: "check", width: 320 }, { key: "observed", width: 110, align: "right" }, { key: "detail", width: 420 }]} />
          </ChartCard>); }}</Async>)}
      {tab === "completeness" && (
        <Async q={dq}>{(d) => {
          const cols = Object.keys(d.completeness_matrix[0] ?? {}).filter((k) => k !== "games_id");
          const max = (c: string) => Math.max(1, ...d.completeness_matrix.map((r: any) => Number(r[c])));
          return (
            <div className="grid gap-4">
              <ChartCard title="Records per edition and dataset" subtitle="Each column is scaled to its own maximum; empty cells = nothing collected" height={520}>
                <Heat diverging={false} domain={[0, 1]} cell={72} rowsLabels={d.completeness_matrix.map((r: any) => r.games_id)} colLabels={cols} values={d.completeness_matrix.map((r: any) => cols.map((c) => Number(r[c]) / max(c)))} format={(v) => (v === 0 ? "0" : "●")} />
              </ChartCard>
              <ChartCard title="Missing edition × dataset combinations" height={200}><DataTable rows={d.missing} columns={[{ key: "games_id", width: 140 }, { key: "dataset" }]} empty="No gaps." /></ChartCard>
            </div>); }}</Async>)}
      {tab === "reconciliation" && (
        <Async q={dq}>{(d) => (
          <ChartCard title="Medal totals: Olympedia podiums vs the Wikipedia tables" subtitle="Olympedia podium counts are the authority (they reproduce official totals); Wikipedia rows are a cross-check and disagree where its table was mis-parsed" height={520}>
            <DataTable rows={d.reconciliation} height={500} exportName="reconciliation" columns={[{ key: "games_id", width: 120 }, { key: "nocs", header: "NOCs", align: "right", width: 70 }, { key: "exact", header: "Exact match", align: "right", width: 110 }, { key: "within2", header: "Within ±2", align: "right", width: 100 }, { key: "not_in_wikipedia", header: "Not in Wikipedia", align: "right", width: 120 }, { key: "olympedia_total", header: "Olympedia medals", align: "right", width: 130 }, { key: "wikipedia_total", header: "Wikipedia medals", align: "right", width: 130 }]} />
          </ChartCard>)}</Async>)}
      {tab === "findings" && (
        <Async q={dq}>{(d) => (<div className="grid gap-4">
          <ChartCard title="Audit findings" subtitle="reports/data_quality/quality_findings.csv" height={400}><DataTable rows={d.findings} height={380} columns={[{ key: "severity", width: 90 }, { key: "dataset", width: 240 }, { key: "finding", width: 320 }, { key: "detail", width: 200 }]} /></ChartCard>
          <ChartCard title="Referential integrity" height={240}><DataTable rows={d.relationships} height={260} columns={[{ key: "relationship", width: 360 }, { key: "orphan_rows", header: "Orphans", align: "right", width: 90 }, { key: "status", width: 100 }]} /></ChartCard>
        </div>)}</Async>)}
      <VizSection page="engineering" />
    </div>
  );
}
