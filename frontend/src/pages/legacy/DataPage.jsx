import { useEffect, useState } from "react";

const get = (path) =>
  fetch(`/api${path}`).then((r) => (r.ok ? r.json() : r.text().then((t) => Promise.reject(new Error(t)))));

// Live data page: choose a warehouse table (or a generated report), filter, page through real rows. Nothing is mocked.
export default function DataPage({ title, tables = [], reports = [], note }) {
  const choices = [
    ...tables.map((t) => ({ kind: "table", name: t })),
    ...reports.map((r) => ({ kind: "report", name: r })),
  ];
  const [sel, setSel] = useState(choices[0]);
  const [f, setF] = useState({ games_id: "", season: "", noc: "", q: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setErr(null);
    if (sel.kind === "report") {
      get(`/reports/${sel.name}`).then(setData).catch((e) => { setData(null); setErr(e.message); });
      return;
    }
    const p = new URLSearchParams({
      page,
      page_size: 50,
      ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)),
    });
    get(`/explorer/${sel.name}?${p}`).then(setData).catch((e) => { setData(null); setErr(e.message); });
  }, [sel, f, page]);

  const rows = data ? (sel.kind === "report" ? data.rows.slice((page - 1) * 50, page * 50) : data.rows) : [];
  const last = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div>
      <h1>{title}</h1>
      {note && <p className="lead">{note}</p>}
      <div className="panel" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select
          value={`${sel.kind}:${sel.name}`}
          onChange={(e) => {
            const [kind, name] = e.target.value.split(":");
            setSel({ kind, name });
            setPage(1);
          }}
        >
          {choices.map((c) => (
            <option key={c.kind + c.name} value={`${c.kind}:${c.name}`}>
              {c.kind === "report" ? "report: " : ""}
              {c.name}
            </option>
          ))}
        </select>
        {sel.kind === "table" &&
          ["games_id", "season", "noc", "q"].map((k) => (
            <input
              key={k}
              placeholder={k === "q" ? "search text" : k}
              value={f[k]}
              onChange={(e) => { setF({ ...f, [k]: e.target.value }); setPage(1); }}
            />
          ))}
        <span>{data ? `${data.total.toLocaleString()} rows` : ""}</span>
      </div>
      {err && <div className="panel">Could not load: {err}</div>}
      {data && (
        <div style={{ overflow: "auto" }}>
          <table>
            <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>{data.columns.map((c) => <td key={c}>{String(r[c] ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button> page {page}/{last}{" "}
          <button disabled={page >= last} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
