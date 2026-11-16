#!/usr/bin/env python3
"""Regenerate data/exports, staging, processed, cleaned from the warehouse (raw files are never touched).
exports   = normalised warehouse tables      staging   = src_* tables loaded from the CSV folder (as received, mojibake repaired)
processed = Olympedia-derived working tables cleaned   = analysis-ready athlete table (only values present in sources; nothing invented)"""
import sqlite3
from pathlib import Path
import pandas as pd
D = Path(__file__).resolve().parents[1]/'data'
c = sqlite3.connect(f'file:{D}/olympics_warehouse.db?mode=ro', uri=True)
def dump(folder, tables):
    for t in tables:
        n = 0; f = D/folder/f'{t}.csv'; f.unlink(missing_ok=True)
        for i, ch in enumerate(pd.read_sql(f'select * from "{t}"', c, chunksize=100000)):
            ch.to_csv(f, mode='a', header=(i == 0), index=False, encoding='utf-8-sig'); n += len(ch)
        print(f'{folder}/{t}.csv {n}', flush=True)
dump('exports', ['games', 'sports', 'disciplines', 'events', 'athletes', 'athlete_id_map', 'athlete_participations', 'event_results', 'medals', 'medal_tables',
                 'teams', 'team_members', 'matches', 'match_results', 'match_statistics', 'venues', 'records', 'historical_nocs', 'countries'])
dump('staging', ['src_athlete_events', 'src_athlete_bios', 'src_athlete_results', 'src_olympics_medallists', 'src_noc_regions'])
dump('processed', ['olympedia_rosters', 'olympedia_matches', 'olympedia_match_players', 'olympedia_match_events', 'olympedia_standings', 'olympedia_country_participation',
                   'olympedia_venues', 'olympedia_venue_usage', 'olympedia_records_current', 'olympedia_records_history'])
cl = pd.read_sql("""select a.athlete_id, a.full_name, a.gender, a.date_of_birth, a.date_of_death, a.height_cm, a.weight_kg, a.source_url,
  count(distinct p.games_id) games_competed, min(p.games_id) first_games, max(p.games_id) last_games, sum(p.medal is not null and p.medal not in ('','NA','None')) medals
  from athletes a left join athlete_participations p on p.athlete_id=a.athlete_id group by a.athlete_id""", c)
cl.loc[(cl.height_cm < 100) | (cl.height_cm > 250), 'height_cm'] = None
cl.loc[(cl.weight_kg < 25) | (cl.weight_kg > 250), 'weight_kg'] = None
(D/'cleaned').mkdir(exist_ok=True); cl.to_csv(D/'cleaned'/'athletes_clean.csv', index=False, encoding='utf-8-sig'); print('cleaned/athletes_clean.csv', len(cl))
