#!/usr/bin/env python3
"""venues <- olympedia_venues x olympedia_venue_usage (one row per venue per Games, sports aggregated). Offline, idempotent.
Wikipedia-sourced rows are kept untouched."""
import sqlite3, re
from pathlib import Path
c = sqlite3.connect(Path(__file__).resolve().parents[1]/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.execute("DELETE FROM venues WHERE source_url LIKE 'https://www.olympedia.org/venues/%'")
c.execute("""INSERT INTO venues(games_id,venue_name,city,country,sport,capacity,latitude,longitude,venue_image,source_url,verification_status,created_at,updated_at)
SELECT u.games_id, COALESCE(NULLIF(v.name,''), v.english_name, 'Venue '||v.venue_id), v.place, NULL, group_concat(DISTINCT u.sport),
       CASE WHEN v.games_capacity GLOB '[0-9]*' THEN CAST(REPLACE(v.games_capacity,',','') AS INTEGER) END,
       v.latitude, v.longitude, NULL, v.source_url, 'collected', datetime('now'), datetime('now')
FROM olympedia_venue_usage u JOIN olympedia_venues v ON v.venue_id=u.venue_id
WHERE u.games_id IS NOT NULL GROUP BY u.games_id, v.venue_id""")
c.commit()
print('venues total', c.execute('select count(*) from venues').fetchone()[0], '| from Olympedia', c.execute("select count(*),sum(latitude is not null),sum(capacity is not null),count(distinct games_id) from venues where source_url like 'https://www.olympedia.org/%'").fetchone())
