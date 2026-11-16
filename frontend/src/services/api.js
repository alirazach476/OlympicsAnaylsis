const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  overview: () => request("/overview"),
  games: (season) => request(`/games${season ? `?season=${season}` : ""}`),
  crawlerSummary: (gamesId) =>
    request(`/crawler/summary${gamesId ? `?games_id=${gamesId}` : ""}`),
  crawlerPages: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/crawler/pages?${q}`);
  },
  crawlerLinks: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/crawler/links?${q}`);
  },
  crawlerQueue: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/crawler/queue?${q}`);
  },
  crawlerHistory: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/crawler/history?${q}`);
  },
  seed: () => request("/crawler/seed", { method: "POST" }),
  startCrawl: (body) =>
    request("/crawler/start", { method: "POST", body: JSON.stringify(body) }),
  pauseCrawl: () => request("/crawler/pause", { method: "POST" }),
  resumeCrawl: (body) =>
    request("/crawler/resume", { method: "POST", body: JSON.stringify(body) }),
};
