import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";

export default function GamesPage({ season }) {
  const [games, setGames] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    api
      .games(season)
      .then(setGames)
      .catch((e) => setError(e.message));
  }, [season]);

  return (
    <div>
      <h1>{season === "summer" ? "Summer" : "Winter"} Olympics</h1>
      <p className="lead">
        {season === "summer" ? "1960–2024" : "1960–2026 (includes Milano Cortina)"}
      </p>
      {error && <div className="error">{error}</div>}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Year</th>
              <th>Host</th>
              <th>Edition</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.games_id}>
                <td>{g.year}</td>
                <td>
                  {g.host_city}, {g.host_country}
                </td>
                <td>{g.official_edition_name}</td>
                <td>
                  <span className="badge warn">{g.verification_status}</span>
                </td>
                <td>
                  <Link to={`/edition/${g.games_id}`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
