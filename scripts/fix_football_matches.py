#!/usr/bin/env python3
"""Repair the football fixtures in `matches` (offline, idempotent, nothing is lost).

Problem: the Wikipedia football parser read the kickoff time ("17:00") as a score (17-0) and the same match was loaded from several Wikipedia pages
(tournament, group, final ...) on top of the Olympedia fixtures, so football had ~4,000 defective or duplicate rows. Olympedia holds one clean row per
match (716 scored football matches 1960-2024), so every Wikipedia-sourced football row is moved to `archived_matches` (with the reason) and removed from
`matches` / `match_results`. The parser itself is fixed (backend/scrapers/wikipedia/football.py), so a re-crawl no longer produces the defect."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
cols = [r[1] for r in c.execute("PRAGMA table_info(matches)")]
c.execute(f"CREATE TABLE IF NOT EXISTS archived_matches AS SELECT *, CAST(NULL AS TEXT) archived_reason, CAST(NULL AS TEXT) archived_at FROM matches WHERE 0")
where = """match_id IN (SELECT m.match_id FROM matches m JOIN sports s ON s.sport_id=m.sport_id
                      WHERE s.sport_name='Football' AND m.source_url LIKE '%wikipedia.org%')"""
n_bad = c.execute(f"""SELECT COUNT(*) FROM matches m JOIN sports s ON s.sport_id=m.sport_id WHERE s.sport_name='Football' AND m.source_url LIKE '%wikipedia.org%'
                      AND LENGTH(m.home_score)=2 AND m.away_score IN ('00','15','30','45')""").fetchone()[0]
n = c.execute(f"SELECT COUNT(*) FROM matches WHERE {where}").fetchone()[0]
if n:
    c.execute(f"""INSERT INTO archived_matches SELECT m.*, 'wikipedia football duplicate of Olympedia fixtures; kickoff time parsed as score in ' || ? || ' rows', datetime('now')
                  FROM matches m WHERE {where}""", (str(n_bad),))
    c.execute(f"DELETE FROM match_results WHERE match_id IN (SELECT match_id FROM archived_matches)")
    c.execute(f"DELETE FROM match_statistics WHERE match_id IN (SELECT match_id FROM archived_matches)")
    c.execute(f"DELETE FROM matches WHERE match_id IN (SELECT match_id FROM archived_matches)")
c.commit()
q = lambda s: c.execute(s).fetchone()[0]
print(f"archived {n} Wikipedia football rows ({n_bad} with a kickoff time as score) | archive total {q('SELECT COUNT(*) FROM archived_matches')} | matches now {q('SELECT COUNT(*) FROM matches')}")
print("football matches left:", q("SELECT COUNT(*) FROM matches m JOIN sports s ON s.sport_id=m.sport_id WHERE s.sport_name='Football'"),
      "| with a score that looks like a clock time:", q("""SELECT COUNT(*) FROM matches m JOIN sports s ON s.sport_id=m.sport_id WHERE s.sport_name='Football'
        AND LENGTH(m.home_score)=2 AND m.away_score IN ('00','15','30','45')"""))
