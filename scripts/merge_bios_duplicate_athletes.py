#!/usr/bin/env python3
"""Merge the 'bios-only' athlete rows (identity 'olympedia:<id>', no participations) into the CSV athlete they are linked to (athlete_id_map: kaggle id <-> Olympedia id).
The CSV athlete keeps its id (all participations / results / medals hang on it); its EMPTY fields (original name, birth / death date, height, weight, biography) are filled from the bios row
and the bios row is deleted.  Every merge is recorded in athletes_merged.  Bios-only rows with no link stay (they are real athletes without a CSV record).  Offline, idempotent."""
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
c.execute("""CREATE TABLE IF NOT EXISTS athletes_merged (bios_athlete_id INTEGER, kept_athlete_id INTEGER, bios_full_name TEXT, bios_identity_key TEXT, merged_at TEXT)""")
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
used = set()
for t in ("athlete_participations", "event_results", "team_members", "medals"):
    used |= {r[0] for r in c.execute(f"SELECT DISTINCT athlete_id FROM {t} WHERE athlete_id IS NOT NULL")}
pairs = [r for r in c.execute("""SELECT a.athlete_id, k.athlete_id, a.full_name, a.identity_key FROM athletes a
    JOIN athlete_id_map m ON m.olympedia_athlete_id = substr(a.identity_key, 11)
    JOIN athletes k ON k.identity_key = 'athlete_events:' || m.kaggle_id
    WHERE a.identity_key LIKE 'olympedia:%' AND k.athlete_id != a.athlete_id""") if r[0] not in used]
for bid, kid, name, ident in pairs:
    c.execute("""UPDATE athletes SET
        original_name = COALESCE(original_name, (SELECT original_name FROM athletes WHERE athlete_id=?)),
        date_of_birth = COALESCE(date_of_birth, (SELECT date_of_birth FROM athletes WHERE athlete_id=?)),
        date_of_death = COALESCE(date_of_death, (SELECT date_of_death FROM athletes WHERE athlete_id=?)),
        height_cm = COALESCE(height_cm, (SELECT height_cm FROM athletes WHERE athlete_id=?)),
        weight_kg = COALESCE(weight_kg, (SELECT weight_kg FROM athletes WHERE athlete_id=?)),
        biography = COALESCE(biography, (SELECT biography FROM athletes WHERE athlete_id=?)),
        gender = COALESCE(gender, (SELECT gender FROM athletes WHERE athlete_id=?))
        WHERE athlete_id=?""", (bid,) * 7 + (kid,))
    c.execute("INSERT INTO athletes_merged VALUES (?,?,?,?,?)", (bid, kid, name, ident, now))
    c.execute("DELETE FROM athletes WHERE athlete_id=?", (bid,))
c.commit()
left = c.execute("SELECT COUNT(*) FROM athletes WHERE identity_key LIKE 'olympedia:%' AND athlete_id NOT IN (SELECT DISTINCT athlete_id FROM athlete_participations)").fetchone()[0]
print(f"merged {len(pairs):,} bios-only duplicates into their CSV athlete; {left:,} bios-only athletes remain (no CSV record linked)")
