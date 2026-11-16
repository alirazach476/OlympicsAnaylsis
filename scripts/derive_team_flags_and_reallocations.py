#!/usr/bin/env python3
"""Offline from saved Olympedia pages/rosters:
 * olympedia_event_notes  <- every <p> note on cached event result pages (data/raw/olympedia/editions/*/events/*.html)
 * medals.is_team_medal   <- athlete's roster row for that medal has a team (olympedia_rosters.team) - unambiguous cases only
 * medals.reallocation_note <- event notes mentioning disqualification / stripped / reallocated / retroactive / re-awarded, attached to
   the medallists of that event (linked athletes only). Raw notes always stay in olympedia_event_notes; nothing is paraphrased."""
import glob, re, sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.executescript("""DROP TABLE IF EXISTS olympedia_event_notes;
CREATE TABLE olympedia_event_notes(id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, event_title TEXT, note TEXT, is_medal_relevant INTEGER, source_url TEXT);""")
REL = re.compile(r'disqualif|stripped|reallocat|retroactiv|re-?awarded|annul|vacated|medal', re.I)
n = 0
for f in glob.glob(str(ROOT/'data/raw/olympedia/editions/*/events/*.html')):
    p = Path(f); gid, rid = p.parent.parent.name, p.stem
    s = BeautifulSoup(p.read_text(encoding='utf-8', errors='replace'), 'lxml')
    title = s.h1.get_text(' ', strip=True) if s.h1 else None
    for e in s.select('p'):
        tx = re.sub(r'\s+', ' ', e.get_text(' ', strip=True))
        if len(tx) > 20 and not tx.startswith('Did you know'):
            rel = int(bool(re.search(r'disqualif|stripped|reallocat|retroactiv|re-?awarded|annul|vacated', tx, re.I) and re.search(r'medal|gold|silver|bronze|result|place', tx, re.I)))
            c.execute('INSERT INTO olympedia_event_notes(games_id,result_id,event_title,note,is_medal_relevant,source_url) VALUES (?,?,?,?,?,?)', (gid, rid, title, tx, rel, f'https://www.olympedia.org/results/{rid}')); n += 1
c.commit(); print('event notes', n, '| medal-relevant', c.execute('select count(*) from olympedia_event_notes where is_medal_relevant=1').fetchone()[0])
# medal -> olympedia roster row, done in pandas (unique per athlete+games+medal_type only)
import pandas as pd
m = pd.read_sql("SELECT m.medal_id, m.athlete_id, m.games_id, m.medal_type, a.identity_key FROM medals m JOIN athletes a ON a.athlete_id=m.athlete_id", c)
m['kid'] = m.identity_key.str.replace('athlete_events:', '', regex=False)
im = pd.read_sql('SELECT kaggle_id kid, olympedia_athlete_id oid FROM athlete_id_map', c)
m = m.merge(im, on='kid')
m = m[m.groupby(['athlete_id', 'games_id', 'medal_type']).medal_id.transform('count') == 1]
ro = pd.read_sql("SELECT athlete_id oid, games_id, noc, event_result_id rid, athlete_name, team FROM olympedia_rosters WHERE athlete_id IS NOT NULL", c)
team_rids = set(ro.loc[ro.team.fillna('').ne(''), 'rid'].astype(str))
st = pd.read_sql("SELECT result_id rid, noc, medal medal_type FROM olympedia_standings WHERE medal IS NOT NULL AND medal!='' AND is_phase=0", c)
st['rid'] = st.rid.astype(str)
# team flag: a roster row of this athlete in a TEAM event whose standings give that NOC this medal
ro['rid'] = ro.rid.astype(str)
jt = m.merge(ro[ro.rid.isin(team_rids)], on=['oid', 'games_id']).merge(st, on=['rid', 'noc', 'medal_type'])
team_ids = set(jt.medal_id)
# reallocation: STRONG wording only, and the athlete's own name must appear in that event's note
STRONG = re.compile(r'stripped of|reallocat|retroactiv|re-?awarded|medal (?:was|were) (?:taken|withdrawn|rescinded|forfeited|stripped|reassigned)|(?:disqualified|banned|suspended) (?:for|after|due to)[^.]{0,60}(?:dop|steroid|positive|drug|testosterone|stimulant|nandrolone)|positive (?:test|sample|drug test)[^.]{0,80}(?:disqualif|stripped|medal)|(?:medal|gold|silver|bronze)[^.]{0,80}(?:later|subsequently|eventually)[^.]{0,60}(?:disqualif|stripped|taken away|rescinded|upgraded)', re.I)
nt = pd.read_sql("SELECT result_id rid, note FROM olympedia_event_notes", c); nt['rid'] = nt.rid.astype(str)
nt = nt[nt.note.map(lambda x: bool(STRONG.search(x)))]
jr = m.merge(ro, on=['oid', 'games_id']).merge(nt, on='rid')
def pick(a, n):
    last = a.split()[-1] if isinstance(a, str) and a.split() else None
    sents = re.split(r'(?<=[.!?])\s+', n)
    for i, x in enumerate(sents):
        if STRONG.search(x) and last and last in ' '.join(sents[max(0, i - 1):i + 1]):  # name in the sentence (or the one just before it)
            return ' '.join(sents[max(0, i - 1):i + 1])
jr['note'] = [pick(a, n) for a, n in zip(jr.athlete_name, jr.note)]
jr = jr[jr.note.notna()]
jr = jr.drop_duplicates('medal_id')
c.execute('UPDATE medals SET is_team_medal=0')
c.execute("UPDATE medals SET reallocation_note=NULL WHERE reallocation_note LIKE 'Olympedia event note:%'")
c.executemany('UPDATE medals SET is_team_medal=1 WHERE medal_id=?', [(int(i),) for i in team_ids])
c.executemany('UPDATE medals SET reallocation_note=? WHERE medal_id=?', [('Olympedia event note: ' + n, int(i)) for i, n in zip(jr.medal_id, jr.note)])
c.commit()
q = lambda s: c.execute(s).fetchall()
print('team medals', q('select count(*) from medals where is_team_medal=1'), 'with reallocation note', q('select count(*) from medals where reallocation_note is not null'))
print(q('select medal_id,games_id,medal_type,substr(reallocation_note,1,220) from medals where reallocation_note is not null limit 6'))
