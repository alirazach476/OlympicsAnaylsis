import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../services/api";

export default function EditionPage() {
  const { gamesId } = useParams();
  const [summary, setSummary] = useState(null);
  const [pages, setPages] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.crawlerSummary(gamesId),
      api.crawlerPages({ games_id: gamesId, limit: 50 }),
    ])
      .then(([s, p]) => {
        setSummary(s);
        setPages(p);
      })
      .catch((e) => setError(e.message));
  }, [gamesId]);

  return (
    <div>
      <h1>Edition {gamesId}</h1>
      <p className="lead">Crawl progress and discovered Wikipedia pages for this edition.</p>
      {error && <div className="error">{error}</div>}
      {summary && (
        <div className="grid">
          <div className="stat"><div className="label">Crawled</div><div className="value">{summary.pages_crawled}</div></div>
          <div className="stat"><div className="label">Pending</div><div className="value">{summary.queue_pending}</div></div>
          <div className="stat"><div className="label">Failed</div><div className="value">{summary.queue_failed}</div></div>
          <div className="stat"><div className="label">Excluded</div><div className="value">{summary.pages_excluded}</div></div>
          <div className="stat"><div className="label">Links</div><div className="value">{summary.links_total}</div></div>
        </div>
      )}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Depth</th>
              <th>Category</th>
              <th>Score</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.wikipedia_page_id}>
                <td>
                  <a href={p.url} target="_blank" rel="noreferrer">
                    {p.title}
                  </a>
                </td>
                <td>{p.crawl_depth}</td>
                <td>{p.page_category}</td>
                <td>{p.relevance_score ?? "—"}</td>
                <td>
                  <span className={`badge ${p.crawl_status === "crawled" ? "ok" : "warn"}`}>
                    {p.crawl_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
