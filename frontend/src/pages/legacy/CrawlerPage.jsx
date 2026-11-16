import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";
import { CsvButton } from "../../components/CsvButton";
import { TableFrame } from "../../components/tables/TableFrame";

export default function CrawlerPage() {
  const [summary, setSummary] = useState(null);
  const [pages, setPages] = useState([]);
  const [queue, setQueue] = useState([]);
  const [links, setLinks] = useState([]);
  const [history, setHistory] = useState([]);
  const [gamesId, setGamesId] = useState("1960_summer");
  const [maxDepth, setMaxDepth] = useState(2);
  const [maxPages, setMaxPages] = useState(15);
  const [minScore, setMinScore] = useState(0.45);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    setError("");
    Promise.all([
      api.crawlerSummary(gamesId || undefined),
      api.crawlerPages({ games_id: gamesId || undefined, limit: 40 }),
      api.crawlerQueue({ games_id: gamesId || undefined, status: "pending", limit: 40 }),
      api.crawlerLinks({ games_id: gamesId || undefined, limit: 40 }),
      api.crawlerHistory({ games_id: gamesId || undefined, limit: 40 }),
    ])
      .then(([s, p, q, l, h]) => {
        setSummary(s);
        setPages(p);
        setQueue(q);
        setLinks(l);
        setHistory(h);
      })
      .catch((e) => setError(e.message));
  }, [gamesId]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const body = {
    games_ids: gamesId ? [gamesId] : null,
    max_depth: Number(maxDepth),
    max_pages_per_edition: Number(maxPages),
    min_relevance_score: Number(minScore),
  };

  async function run(action) {
    setBusy(true);
    setError("");
    try {
      if (action === "seed") await api.seed();
      if (action === "start") await api.startCrawl(body);
      if (action === "pause") await api.pauseCrawl();
      if (action === "resume") await api.resumeCrawl(body);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Wikipedia Crawler</h1>
      <p className="lead">
        BFS crawl of Olympic edition seed pages via the MediaWiki API. Resume-safe; excludes
        low-relevance encyclopedia drift.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="toolbar">
        <label>
          games_id{" "}
          <input value={gamesId} onChange={(e) => setGamesId(e.target.value)} placeholder="1960_summer" />
        </label>
        <label>
          depth{" "}
          <input type="number" value={maxDepth} onChange={(e) => setMaxDepth(e.target.value)} style={{ width: 70 }} />
        </label>
        <label>
          max pages{" "}
          <input type="number" value={maxPages} onChange={(e) => setMaxPages(e.target.value)} style={{ width: 80 }} />
        </label>
        <label>
          min score{" "}
          <input type="number" step="0.05" value={minScore} onChange={(e) => setMinScore(e.target.value)} style={{ width: 80 }} />
        </label>
        <button disabled={busy} onClick={() => run("seed")}>Seed</button>
        <button disabled={busy} onClick={() => run("start")}>Start</button>
        <button className="secondary" disabled={busy} onClick={() => run("pause")}>Pause</button>
        <button disabled={busy} onClick={() => run("resume")}>Resume</button>
        <button className="secondary" disabled={busy} onClick={refresh}>Refresh</button>
      </div>

      {summary && (
        <div className="grid">
          <div className="stat"><div className="label">Crawled</div><div className="value">{summary.pages_crawled}</div></div>
          <div className="stat"><div className="label">Pending</div><div className="value">{summary.queue_pending}</div></div>
          <div className="stat"><div className="label">In progress</div><div className="value">{summary.queue_in_progress}</div></div>
          <div className="stat"><div className="label">Failed</div><div className="value">{summary.queue_failed}</div></div>
          <div className="stat"><div className="label">Excluded</div><div className="value">{summary.pages_excluded}</div></div>
          <div className="stat"><div className="label">Links included</div><div className="value">{summary.links_included}</div></div>
          <div className="stat"><div className="label">Paused</div><div className="value">{summary.paused ? "yes" : "no"}</div></div>
        </div>
      )}

      <div className="panel">
        <h3>Pending queue</h3>
        <TableFrame title="Pending queue" variant="analytics" actions={<CsvButton name="crawler_pending_queue" headers={["title", "depth", "score", "category", "parent"]} rows={queue.map((q) => [q.title, q.depth, q.relevance_score, q.page_category, q.parent_url])} />}>
        <table>
          <thead>
            <tr><th>Title</th><th>Depth</th><th>Score</th><th>Category</th><th>Parent</th></tr>
          </thead>
          <tbody>
            {queue.map((q) => (
              <tr key={q.queue_id}>
                <td>{q.title}</td>
                <td>{q.depth}</td>
                <td>{q.relevance_score ?? "—"}</td>
                <td>{q.page_category}</td>
                <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>{q.parent_url || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableFrame>
      </div>

      <div className="panel">
        <h3>Crawled / discovered pages</h3>
        <TableFrame title="Crawled / discovered pages" variant="analytics" actions={<CsvButton name="crawler_pages" headers={["title", "depth", "status", "score", "parent"]} rows={pages.map((p) => [p.title, p.crawl_depth, p.crawl_status, p.relevance_score, p.parent_url])} />}>
        <table>
          <thead>
            <tr><th>Title</th><th>Depth</th><th>Status</th><th>Score</th><th>Parent</th></tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.wikipedia_page_id}>
                <td><a href={p.url} target="_blank" rel="noreferrer">{p.title}</a></td>
                <td>{p.crawl_depth}</td>
                <td><span className={`badge ${p.crawl_status === "crawled" ? "ok" : "warn"}`}>{p.crawl_status}</span></td>
                <td>{p.relevance_score ?? "—"}</td>
                <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>{p.parent_url || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableFrame>
      </div>

      <div className="panel">
        <h3>Link graph (recent)</h3>
        <TableFrame title="Link graph (recent)" variant="analytics" actions={<CsvButton name="crawler_links" headers={["from", "to", "depth", "score", "included"]} rows={links.map((l) => [l.source_page_title, l.destination_page_title, l.crawl_depth, l.relevance_score, l.included ? "yes" : "no"])} />}>
        <table>
          <thead>
            <tr><th>From</th><th>To</th><th>Depth</th><th>Score</th><th>Included</th></tr>
          </thead>
          <tbody>
            {links.map((l) => (
              <tr key={l.wikipedia_link_id}>
                <td>{l.source_page_title}</td>
                <td>{l.destination_page_title}</td>
                <td>{l.crawl_depth}</td>
                <td>{l.relevance_score ?? "—"}</td>
                <td>
                  {l.included ? (
                    <span className="badge ok">yes</span>
                  ) : (
                    <span className="badge err" title={l.exclusion_reason || ""}>no</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableFrame>
      </div>

      <div className="panel">
        <h3>Crawl log</h3>
        <TableFrame title="Crawl log" variant="analytics" actions={<CsvButton name="crawler_log" headers={["when", "action", "status", "depth", "message"]} rows={history.map((h) => [h.occurred_at, h.action, h.status, h.depth, h.message])} />}>
        <table>
          <thead>
            <tr><th>When</th><th>Action</th><th>Status</th><th>Depth</th><th>Message</th></tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.history_id}>
                <td>{h.occurred_at}</td>
                <td>{h.action}</td>
                <td>{h.status}</td>
                <td>{h.depth ?? "—"}</td>
                <td>{h.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableFrame>
      </div>
    </div>
  );
}
