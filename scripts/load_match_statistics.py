#!/usr/bin/env python3
"""Fill match_statistics from saved Olympedia match pages (olympedia_match_players). Offline, idempotent.
One row per player appearance (coaches / team-total rows excluded). Nothing is invented: absent stats stay NULL;
every original stat is preserved in extra_stats_json together with player name and Olympedia athlete id."""
import json, re, sqlite3
from pathlib import Path
c = sqlite3.connect(Path(__file__).resolve().parents[1]/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
num = lambda v: int(m.group(0)) if v and (m := re.fullmatch(r'\s*\d+\s*', v)) else None
c.execute("DELETE FROM match_statistics WHERE source_url LIKE 'https://www.olympedia.org/results/%'")
amap = {o: k for k, o in c.execute('select kaggle_id, olympedia_athlete_id from athlete_id_map')}
aid = {k: a for k, a in c.execute("select substr(identity_key,16), athlete_id from athletes where identity_key like 'athlete_events:%'")}
mm = {u.rsplit('/', 1)[1]: (i, h, a) for i, u, h, a in c.execute("select match_id,source_url,home_team_id,away_team_id from matches where source_url like 'https://www.olympedia.org/results/%'")}
rows = []; n = 0
for gid, rid, ti, name, oid, stats in c.execute("select games_id,result_id,team_index,player_name,athlete_id,stats_json from olympedia_match_players where is_coach=0 and is_team_total=0"):
    m = mm.get(rid)
    if not m: continue
    s = json.loads(stats or '{}')
    cards = [num(s.get(k)) for k in ('Yellow Cards', 'Red Cards')]
    rows.append((m[0], aid.get(amap.get(oid)) if oid else None, m[1] if ti == 1 else m[2] if ti == 2 else None,
                 num(s.get('Goals')), num(s.get('Assists')), num(s.get('Points')),
                 sum(x for x in cards if x is not None) if any(x is not None for x in cards) else None,
                 num(s.get('Penalties in Minutes (PIM)')), None,
                 json.dumps({'player': name, 'olympedia_athlete_id': oid, 'stats': s}, ensure_ascii=False),
                 f'https://www.olympedia.org/results/{rid}', 'collected'))
c.executemany("INSERT INTO match_statistics(match_id,athlete_id,team_id,goals,assists,points,cards,penalties,minutes_played,extra_stats_json,source_url,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))", rows)
c.commit()
print('match_statistics rows', len(rows), '| linked to athlete', sum(r[1] is not None for r in rows), '| with team', sum(r[2] is not None for r in rows), '| with goals', sum(r[3] is not None for r in rows))
