import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .overview()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1>Collection Overview</h1>
      <p className="lead">
        Live counts from PostgreSQL. Empty domains mean not yet collected — not invented.
      </p>
      {error && <div className="error">{error}</div>}
      {stats && (
        <div className="grid">
          <div className="stat"><div className="label">Games</div><div className="value">{stats.games_total}</div></div>
          <div className="stat"><div className="label">Summer</div><div className="value">{stats.summer_games}</div></div>
          <div className="stat"><div className="label">Winter</div><div className="value">{stats.winter_games}</div></div>
          <div className="stat"><div className="label">Wiki crawled</div><div className="value">{stats.wikipedia_pages_crawled}</div></div>
          <div className="stat"><div className="label">Wiki discovered</div><div className="value">{stats.wikipedia_pages_discovered}</div></div>
          <div className="stat"><div className="label">Pending</div><div className="value">{stats.crawl_pending}</div></div>
          <div className="stat"><div className="label">Failed</div><div className="value">{stats.crawl_failed}</div></div>
          <div className="stat"><div className="label">Links</div><div className="value">{stats.links_discovered}</div></div>
          <div className="stat"><div className="label">Athletes</div><div className="value">{stats.athletes}</div></div>
          <div className="stat"><div className="label">Events</div><div className="value">{stats.events}</div></div>
          <div className="stat"><div className="label">Results</div><div className="value">{stats.results}</div></div>
          <div className="stat"><div className="label">Medal rows</div><div className="value">{stats.medal_table_rows}</div></div>
        </div>
      )}
      <div className="panel">
        <p>
          Start with the <Link to="/crawler">Wikipedia Crawler</Link> page to seed and run BFS
          collection for one or more editions.
        </p>
      </div>
    </div>
  );
}
