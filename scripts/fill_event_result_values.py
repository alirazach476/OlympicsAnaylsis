#!/usr/bin/env python3
"""event_results.final_position / result_value / result_unit / result_status <- Olympedia (offline, idempotent, empty fields only, nothing invented).

Each event_results row (Kaggle-style event name, e.g. "Gymnastics Men's Horse Vault") is matched to the athlete's Olympedia entry in the same Games
(olympedia_athlete_results: sport + event, e.g. "Artistic Gymnastics / Vault, Men") by Olympedia id when linked, else by NOC + normalised name.
An event matches when every word of the Olympedia event is contained in the warehouse event name; the longest match must be unique.
Second pass for what the strict pass cannot place (never guessing - every rule needs a UNIQUE answer):
  * names: the CSV carries full names and nicknames ('Kornelia "Corrie" Winkel (-Vink)'), Olympedia the name used in competition ('Corrie Winkel'); an Olympedia name of
    2+ words that is a subset of the CSV name, in the same Games and NOC, identifies the athlete
  * events: the two sources word events differently ('Pommelled Horse' / 'Pommel Horse, Men', 'Curling' / 'Team, Men'); among the athlete's own Olympedia events in a
    compatible sport, the one sharing at least half of its words (including a meaningful word) is chosen, and only when no other event ties with it

The mark (time / distance / score) is stored only for events whose unit is recognised (time, distance, points, weight); for ball and team sports the numbers in the
round tables are group goals or set ratios, not an athlete's mark, so those stay empty. The mark is looked up in this order and the first hit wins:
  1. the event's MAIN results table (olympedia_event_rows is_main=1: competitor name + NOC)
  2. the athlete's own standings row (olympedia_standings, athlete id from extra_json)
  3. any ROUND table of the event (heats, qualification, semi-finals ...) by competitor name + NOC - the best mark by the event's direction
     (lower is better for times, higher for distances / points); where the direction is unknown the earliest table is used
  4. for team entries (crew / squad listed under the country name) the team's mark, only when the country has exactly one entry in that event
Positions: final_position comes from the main table; a clean number in olympedia_athlete_results.position is the fallback (positions like '7 h6 r1/4'
are a place inside a heat, not a final standing, so they are not used). Non-numeric outcomes (DNF / DNS / DQ / AC ...) go to result_status.
result_value is stored as recorded without the rank in brackets ('55.2 (1)' -> '55.2'); result_unit says what it is (seconds, metres, points, kg)."""
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.viz.charts_sports import parse_value, unit_for  # noqa: E402

c = sqlite3.connect(ROOT / 'data/olympics_warehouse.db', timeout=300)
c.execute('PRAGMA busy_timeout=300000')


def tok(s):
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', str(s or '')) if not unicodedata.combining(ch)).lower()
    s = s.replace("men's", 'men').replace("women's", 'women')
    return frozenset(re.sub(r'[^a-z0-9 ]', ' ', s.replace(',', '')).split())


def nm(s):
    s = re.sub(r'\(.*?\)', ' ', str(s or '')).replace('•', ' ')
    s = ''.join(ch for ch in s if ord(ch) < 128).lower()
    return ' '.join(sorted(re.sub(r'[^a-z ]', ' ', s).split()))


def clean_mark(text):
    """'55.2 (1)' -> '55.2', '10.0w (2.8 m/s)' -> '10.0', '1:47.5' stays."""
    t = str(text or '').strip().split(' ')[0]
    return re.sub(r'[A-Za-z*]+$', '', t) or None


link = pd.read_sql("""SELECT a.athlete_id, a.full_name, COALESCE(m.olympedia_athlete_id,
         CASE WHEN a.identity_key LIKE 'olympedia:%' THEN substr(a.identity_key,11) END) oid
       FROM athletes a LEFT JOIN athlete_id_map m ON m.kaggle_id=substr(a.identity_key,16)""", c)
er = pd.read_sql("""SELECT result_id, games_id, event_name, athlete_id, noc_code noc FROM event_results
                    WHERE final_position IS NULL OR result_value IS NULL OR result_value='' OR result_unit IS NULL""", c).merge(link, on='athlete_id', how='left')
ol = pd.read_sql("SELECT games_id, athlete_id oid, athlete_name, noc, sport, event, position, team FROM olympedia_athlete_results", c)

# ---- mark sources --------------------------------------------------------------------------------------------------------------------------
evr = pd.read_sql("SELECT games_id, sport_name sport, event_name event, competitor, noc, position, result_text, is_main, table_index, phase FROM olympedia_event_rows ORDER BY id", c)
evr['nk'] = evr.competitor.map(nm)
by_name, by_team, by_phase = defaultdict(list), defaultdict(list), defaultdict(list)
for r in evr.itertuples():
    v = parse_value(r.result_text)
    if r.phase:
        by_phase[(r.games_id, r.sport, r.event, r.noc, r.nk)].append((str(r.phase), str(r.position or '').strip()))
    by_name[(r.games_id, r.sport, r.event, r.noc, r.nk)].append((r.is_main, r.table_index or 99, r.position, r.result_text, v))
    by_team[(r.games_id, r.sport, r.event, r.noc)].append((r.is_main, r.table_index or 99, r.position, r.result_text, v, r.nk))
st = pd.read_sql("""SELECT games_id, sport_name sport, event_name event, json_extract(extra_json,'$.athlete_id') oid, is_phase, position, result_value
                    FROM olympedia_standings WHERE json_extract(extra_json,'$.athlete_id') IS NOT NULL ORDER BY id""", c)
by_oid = defaultdict(list)
for r in st.itertuples():
    by_oid[(r.games_id, r.sport, r.event, str(r.oid))].append((1 - int(r.is_phase or 0), 50, r.position, r.result_value, parse_value(r.result_value)))


MIN_TIME = 8.0


def pick(cands, lower):
    """Best candidate: a main-table mark wins; otherwise the best numeric mark by direction (earliest table when the direction is unknown)."""
    numeric = [x for x in cands if x[4] is not None and not (lower and x[4] < MIN_TIME)]   # a 'time' under 8 s is a penalty or place count, not a mark
    if not numeric:
        return None
    main = [x for x in numeric if x[0] == 1]
    if main:
        return min(main, key=lambda x: x[1])
    if lower is None:
        return min(numeric, key=lambda x: x[1])
    return (min if lower else max)(numeric, key=lambda x: x[4])


ol['nk'] = ol.athlete_name.map(nm)
ol['E'] = ol.event.map(tok)
ol['NS'] = ol.nk.map(lambda v: frozenset(v.split()))
o_oid, o_name, o_name_any, o_games_noc = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
for r in ol.itertuples():
    o_oid[(r.games_id, str(r.oid))].append(r)
    o_name[(r.games_id, r.noc, r.nk)].append(r)
    o_name_any[(r.games_id, r.nk)].append(r)
    o_games_noc[(r.games_id, r.noc)].append(r)

GENERIC = {'men', 'women', 'mixed', 'open', 'events', 'event'}
pref = lambda words: {w[:5] for w in words}


def choose(cands, T):
    """The Olympedia entry (one event) that belongs to a warehouse event wording T, or None unless the answer is unique."""
    strict = [x for x in cands if x.E and x.E <= T]
    if strict:
        best = max(len(x.E) for x in strict)
        top = {(x.sport, x.event): x for x in strict if len(x.E) == best}
        return next(iter(top.values())) if len(top) == 1 else None
    tp = pref(T)
    comp = [x for x in cands if x.E and (pref(tok(x.sport)) & tp)]
    scored = []
    for x in comp:
        inter = x.E & T
        frac = len(inter) / len(x.E)
        if frac >= 0.5 and ((inter - GENERIC) or len({(y.sport, y.event) for y in comp}) == 1):
            scored.append((frac, len(inter), x))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], -t[1]))
    top = [t for t in scored if (t[0], t[1]) == (scored[0][0], scored[0][1])]
    return top[0][2] if len({(t[2].sport, t[2].event) for t in top}) == 1 else None


ROUND_WORD = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}
def mhr_round(x):
    m = re.match(r'^\s*=?(?:\d+)?\s*(?:h\d+)?\s*r(\d+/\d+)\s*$', str(x.position or ''))
    return m.group(1) if m else None
er['nk'] = er.full_name.map(nm)
ups, n_matched, n_second = [], 0, 0
maprows = []   # which Olympedia athlete / event each event_results row was matched to (used by fill_event_marks_from_rounds.py)
for r in er.itertuples():
    T = tok(r.event_name)
    x = None
    cands = o_oid.get((r.games_id, str(r.oid)), []) if isinstance(r.oid, str) else []
    if cands:
        x = choose(cands, T)
    if x is None and not cands:
        cands = o_name.get((r.games_id, r.noc, r.nk), []) or (o_name_any.get((r.games_id, r.nk), []) if not isinstance(r.noc, str) else [])
        if cands:
            x = choose(cands, T)
    if x is None and not cands and isinstance(r.noc, str):
        B = frozenset(r.nk.split())
        pool = [y for y in o_games_noc.get((r.games_id, r.noc), []) if len(y.NS) >= 2 and (y.NS <= B or (len(B) >= 2 and B <= y.NS))]
        found = {}
        for oid in {str(y.oid) for y in pool}:
            ch = choose([y for y in pool if str(y.oid) == oid], T)
            if ch is not None:
                found[oid] = ch
        if len(found) == 1:
            x = next(iter(found.values()))
            n_second += 1
    if x is None:
        continue
    n_matched += 1
    maprows.append((r.result_id, x.games_id, str(x.oid), x.sport, x.event))
    label, lower = unit_for(x.event)
    known = not label.startswith('Result as recorded')
    direction = lower if known else None
    # 1-3: athlete rows (main table by name, standings by id, any round table by name)
    cand = list(by_name.get((x.games_id, x.sport, x.event, x.noc, x.nk), [])) + list(by_oid.get((x.games_id, x.sport, x.event, str(x.oid)), []))
    got = pick(cand, direction)
    pos_src = [t for t in cand if t[0] == 1 and t[2] not in (None, '')]
    # 4: team entry under the country name (unique per country and event)
    if got is None and x.team:
        team_rows = [t[:5] for t in by_team.get((x.games_id, x.sport, x.event, x.noc), []) if t[5] == nm(x.team) or t[5] == nm(x.noc)]
        got = pick(team_rows, direction) if team_rows else None
        if not pos_src:
            pos_src = [t for t in team_rows if t[0] == 1 and t[2] not in (None, '')]
    raw_pos = (pos_src[0][2] if pos_src else None) or x.position or ''
    mnum = re.match(r'^=?(\d+)$', str(raw_pos).strip())
    final = int(mnum.group(1)) if mnum else None
    if final is None and mhr_round(x):
        # not in the main table: the athlete's place in the round they went out in ('Round One' lists every competitor ranked, e.g. '=74')
        want = 'round ' + ROUND_WORD.get(int(mhr_round(x).split('/')[0]), '?')
        hits = [pp for ph, pp in by_phase.get((x.games_id, x.sport, x.event, x.noc, x.nk), []) if ph.lower().startswith(want) and re.match(r'^=?\d+$', pp)]
        if len(hits) == 1:
            final = int(hits[0].lstrip('='))
    status = None
    if not mnum:
        m2 = re.match(r'^(DNF|DNS|DQ|AC|NM|NP|DSQ)\b', str(x.position or '').strip())
        status = m2.group(1) if m2 else None
    value = clean_mark(got[3]) if (got and known) else None   # team / ball sports have no athlete mark (their 'values' are group goals or set ratios)
    unit = ('seconds' if lower else 'metres' if 'Distance' in label else 'kg' if 'kg' in label else 'points') if (got and known) else None
    # 'N hH rK/T' = N-th in heat H, round K of T (Olympedia's codes): heat / round / qualification position of the round the athlete reached
    mhr = re.match(r'^\s*=?(\d+)?\s*(?:h(\d+))?\s*(?:r(\d+/\d+))?\s*$', str(x.position or ''))
    heat = rnd = qpos = None
    if mhr and (mhr.group(2) or mhr.group(3)):
        heat = int(mhr.group(2)) if mhr.group(2) else None
        rnd = mhr.group(3)
        qpos = int(mhr.group(1)) if mhr.group(1) else None
    ups.append((final, value, unit, status, heat, rnd, qpos, r.result_id))

c.execute("DROP TABLE IF EXISTS event_result_olympedia_map")
c.execute("CREATE TABLE event_result_olympedia_map (result_id INTEGER PRIMARY KEY, games_id TEXT, oid TEXT, sport TEXT, event TEXT)")
c.executemany("INSERT OR REPLACE INTO event_result_olympedia_map VALUES (?,?,?,?,?)", maprows)
c.executemany("""UPDATE event_results SET final_position=COALESCE(final_position,?),
                 result_value=CASE WHEN result_value IS NULL OR result_value='' THEN ? ELSE result_value END,
                 result_unit=CASE WHEN (result_unit IS NULL OR result_unit='') AND ? IS NOT NULL THEN ? ELSE result_unit END,
                 result_status=CASE WHEN ? IS NOT NULL THEN ? ELSE result_status END,
                 heat=COALESCE(heat,?), round=COALESCE(round,?), qualification_position=COALESCE(qualification_position,?) WHERE result_id=?""",
              [(a, b, u, u, s, s, h, rd, qp, i) for a, b, u, s, h, rd, qp, i in ups])
c.commit()
# ---- validate every stored value: it must be a real mark (time / distance / score). Table placeholders ('-', 'same time', 'at 1 lap', '[DQ]'),
# margins ('+0.3') and zero penalties are not marks and are cleared; '2-31:15' is normalised to '2:31:15'; the unit is set from the event.
HYPHEN_TIME = re.compile(r'^(\d+)-(\d{1,2}):(\d{2}(?:\.\d+)?)$')
rows = c.execute("SELECT result_id, event_name, result_value, result_unit FROM event_results WHERE result_value IS NOT NULL AND result_value!=''").fetchall()
fix = []
for rid, evn, val, unit in rows:
    v = str(val).strip()
    m = HYPHEN_TIME.match(v)
    if m:
        v = f"{m.group(1)}:{m.group(2).zfill(2)}:{m.group(3)}"
    label, lower = unit_for(evn)
    if lower:   # times: a comma can only be a decimal comma ('45,266' = 45.266 s)
        v = re.sub(r'^(\d+(?::\d+)*),(\d+)$', r'.', v)
    elif re.match(r'^\d{1,3}(,\d{3})+(\.\d+)?$', v):   # scores / weights: thousands comma ('1,985' = 1985)
        v = v.replace(',', '')
    elif re.match(r'^\d+,\d{1,2}$', v):   # one or two digits after a comma cannot be thousands: decimal comma ('1,23' = 1.23)
        v = v.replace(',', '.')
    cv = clean_mark(v)
    num = parse_value(cv) if cv else None
    ok = num is not None and not str(cv).startswith('+') and not (lower and num < MIN_TIME)
    ok = ok and not label.startswith('Result as recorded')
    nv = cv if ok else None
    nu = None if nv is None else (unit or (None if label.startswith('Result as recorded') else 'seconds' if lower else 'metres' if 'Distance' in label else 'kg' if 'kg' in label else 'points'))
    if nv != val or nu != unit:
        fix.append((nv, nu, rid))
c.executemany("UPDATE event_results SET result_value=?, result_unit=? WHERE result_id=?", fix)
c.commit()

q = lambda s: c.execute(s).fetchone()[0]
tot = q("SELECT COUNT(*) FROM event_results")
n_pos = q("SELECT COUNT(final_position) FROM event_results")
n_val = q("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!=''")
n_unit = q("SELECT COUNT(*) FROM event_results WHERE result_unit IS NOT NULL")
n_stat = q("SELECT COUNT(*) FROM event_results WHERE result_status!='recorded'")
print(f"rows matched to an Olympedia entry {n_matched:,} of {len(er):,} candidate rows ({n_second:,} through the name-subset pass); {len(fix):,} earlier values normalised")
print(f"event_results now: final_position {n_pos:,} ({100 * n_pos / tot:.0f}%) | result_value {n_val:,} ({100 * n_val / tot:.0f}%) | result_unit {n_unit:,} | status != recorded {n_stat:,} of {tot:,}")
