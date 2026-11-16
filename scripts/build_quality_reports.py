#!/usr/bin/env python3
"""Per-edition completeness + cross-source checks from the warehouse (offline, read-mostly).
Writes reports/completeness/completeness_report.csv, reports/quality/{duplicate_records,missing_records,source_verification_report}.csv,
reports/scraping/crawl_summary.json and one data_quality_reports row per edition. Never marks anything 'complete'."""
import csv, json, sqlite3, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
one = lambda q, *a: c.execute(q, a).fetchone()[0]
def w(path, rows, cols):
    p = ROOT/path; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f); wr.writerow(cols); wr.writerows(rows)
games = c.execute('select games_id,year,season from games order by year,season').fetchall()
rep, missing, ver = [], [], []
for gid, yr, se in games:
    m = dict(
        events=one('select count(*) from events where games_id=?', gid),
        results=one('select count(*) from event_results where games_id=?', gid),
        participations=one('select count(*) from athlete_participations where games_id=?', gid),
        athletes=one('select count(distinct athlete_id) from athlete_participations where games_id=?', gid),
        medal_awards=one('select count(*) from medals where games_id=?', gid),
        medal_table_rows=one('select count(*) from medal_tables where games_id=? and table_scope="country"', gid) if False else one('select count(*) from medal_tables where games_id=?', gid),
        matches=one('select count(*) from matches where games_id=?', gid),
        venues=one('select count(*) from venues where games_id=?', gid),
        nocs=one('select count(distinct noc_code) from athlete_participations where games_id=?', gid),
        pictograms=one("select count(*) from assets where games_id=? and asset_type='sport_pictogram'", gid),
        csv_rows_athlete_events=one('select count(*) from src_athlete_events where Year=? and Season=?', str(yr), se),
        orphan_results=one('select count(*) from event_results r where games_id=? and athlete_id is not null and not exists(select 1 from athletes a where a.athlete_id=r.athlete_id)', gid),
        dup_participations=one('select count(*) from (select 1 from athlete_participations where games_id=? group by athlete_id,event_id having count(*)>1)', gid),
        gold_awards=one('select count(*) from medals where games_id=? and medal_type="Gold"', gid),
        gold_in_table=one('select coalesce(sum(gold),0) from medal_tables where games_id=?', gid),
        missing_dates=one('select (opening_date is null)+(closing_date is null) from games where games_id=?', gid),
        missing_host=one('select (host_city is null)+(host_country is null) from games where games_id=?', gid),
    )
    m['medal_award_vs_table_gold_diff'] = m['gold_awards'] - m['gold_in_table']
    rep.append((gid, yr, se, *m.values()))
    for k in ('events', 'results', 'participations', 'medal_awards', 'medal_table_rows', 'matches', 'venues', 'pictograms'):
        if m[k] == 0: missing.append((gid, k, 'no rows collected'))
    if m['missing_dates'] or m['missing_host']: missing.append((gid, 'games_fields', f"{m['missing_dates']} date + {m['missing_host']} host fields null"))
    ver.append((gid, m['participations'], m['csv_rows_athlete_events'], 'agree' if m['participations'] and m['csv_rows_athlete_events'] and abs(m['participations']-m['csv_rows_athlete_events'])/m['csv_rows_athlete_events'] < .05 else 'differs_or_missing'))
    c.execute('insert into data_quality_reports(games_id,report_type,metrics_json,report_path,generated_at,created_at,updated_at) values(?,?,?,?,?,?,?)',
              (gid, 'completeness', json.dumps(m), 'reports/completeness/completeness_report.csv', *(dt.datetime.utcnow().isoformat(),) * 3))
cols = ['games_id', 'year', 'season', *m.keys()]
w('reports/completeness/completeness_report.csv', rep, cols)
w('reports/quality/missing_records.csv', missing, ['games_id', 'dataset', 'note'])
w('reports/verification/source_verification_report.csv', ver, ['games_id', 'warehouse_participations', 'kaggle_style_csv_rows', 'status'])
dups = c.execute('select athlete_id,games_id,event_id,count(*) from athlete_participations group by 1,2,3 having count(*)>1 limit 50000').fetchall()
w('reports/quality/duplicate_records.csv', dups, ['athlete_id', 'games_id', 'event_id', 'copies'])
q = lambda s: one(s)
summ = dict(generated_at=dt.datetime.utcnow().isoformat(), games=len(games), pages_discovered=q('select count(*) from wikipedia_pages'), crawl_queue=dict(c.execute('select status,count(*) from crawl_queue group by 1').fetchall()), links=q('select count(*) from wikipedia_links'))
(ROOT/'reports/scraping/crawl_summary.json').write_text(json.dumps(summ, indent=2))
c.commit()
print(f'{len(games)} editions | missing flags {len(missing)} | duplicate groups {len(dups)}')
for r in missing[:0]: pass
from collections import Counter
print(Counter(d for _, d, _ in missing))
