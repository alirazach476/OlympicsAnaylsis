#!/usr/bin/env python3
"""Phase 11: indexes for every dashboard filter + ANALYZE. Idempotent."""
import sqlite3, time
from pathlib import Path
c = sqlite3.connect(Path(__file__).resolve().parents[1] / "data/olympics_warehouse.db", timeout=300)
IDX = [
 "gold_event_results(games_id)", "gold_event_results(sport_name, event_name)", "gold_event_results(noc)", "gold_event_results(medal)", "gold_event_results(year)",
 "gold_country_medals(noc_code, year)", "gold_country_medals(games_id, rank_by_gold_silver_bronze)", "gold_sport_performance(sport_id, year)", "gold_sport_performance(games_id)",
 "gold_gender_participation(games_id)", "gold_team_sports(games_id, sport_name)", "gold_athlete_career(full_name)", "gold_athlete_career(medals DESC)", "gold_athlete_career(games_count DESC)",
 "gold_records(games_id)", "silver_participations(games_id, noc_code)", "silver_participations(sport_id)", "silver_participations(games_id, sport_id)", "silver_medal_awards(noc_code)", "silver_medal_awards(sport_id)",
 "olympedia_matches(games_id, sport_name)", "olympedia_matches(sport_name)", "olympedia_podium_results(sport_name, event_name)", "analytics_results(module)", "venues(games_id)",
]
for i, spec in enumerate(IDX):
    t = spec.split("(")[0]
    if c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone():
        c.execute(f"CREATE INDEX IF NOT EXISTS ix_opt_{i} ON {spec}")
t = time.time(); c.execute("ANALYZE"); c.commit()
print(f"{len(IDX)} indexes ensured, ANALYZE {time.time()-t:.1f}s")
