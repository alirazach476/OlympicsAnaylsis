#!/usr/bin/env python3
"""records <- olympedia_records_history (full record progression; current records are its last rows). Offline, idempotent."""
import sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS
by_ed = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.execute("DELETE FROM records WHERE source_url LIKE 'https://www.olympedia.org/records/%'")
amap = {o: k for k, o in c.execute('select kaggle_id, olympedia_athlete_id from athlete_id_map')}
aid = {k: a for k, a in c.execute("select substr(identity_key,16), athlete_id from athletes where identity_key like 'athlete_events:%'")}
cur = {(r[0], r[1]) for r in c.execute('select event_page, record_value||"|"||games from olympedia_records_current where 1=0')}
rows = []
for ep, ev, seq, val, flag, ath, ids, noc, games, ed, date, phase, rank, res, src in c.execute('select event_page,event,seq,record_value,record_flag,athletes,athlete_ids,noc,games,edition_id,record_date,phase,rank,result_url,source_url from olympedia_records_history'):
    first = ids.split(',')[0] if ids else None
    rows.append((by_ed.get(ed), None, aid.get(amap.get(first)) if first else None, noc or None, flag or 'Best performance', val,
                 date or None, f'{ev} | {phase} | {ath} | {games}' + (f' | result {res}' if res else ''), src, 'collected'))
c.executemany("INSERT INTO records(games_id,event_id,athlete_id,noc_code,record_type,record_value,record_unit,record_date,description,source_url,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,NULL,?,?,?,?,datetime('now'),datetime('now'))", [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]) for r in rows])
c.commit()
print('records', c.execute('select count(*) from records').fetchone()[0], c.execute('select record_type,count(*) from records group by 1 order by 2 desc limit 6').fetchall(), 'with athlete', c.execute('select count(*) from records where athlete_id is not null').fetchone()[0])
