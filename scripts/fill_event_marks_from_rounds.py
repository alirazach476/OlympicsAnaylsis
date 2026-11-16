#!/usr/bin/env python3
"""Fill the EMPTY marks / round fields of event_results from olympedia_round_results (every round, heat, pool and qualifying table of the event pages), offline and idempotent.

event_results holds one row per athlete per event: that athlete's result in the LAST round they reached. For each row still empty this takes the athlete's highest-stage round row of the event
(final > semi-final > quarter-final > rounds > heats / qualifying / pools) and fills, only where the field is NULL:
  result_value + result_unit   the mark of that round (time, distance, points, weight) when it is a plain, recognised mark - never a placeholder, a gap ('at 0:00') or a bout score.
                               The unit comes from the event name or from the round table's own header ('Time', 'Points', 'Weight (kg)').
  round / heat / qualification_position   the round name, the heat number and the place IN THAT ROUND
  final_position               the overall place from the event's main table ('7', '=74'), or the place in a final round; a place in a heat is not an overall place
Matching: (1) the Olympedia athlete id already linked to the row; (2) otherwise Games + sport + NOC + the athlete's name words (accent-tolerant) + the event's words - only when exactly ONE athlete
fits (checked against the id-based links: 5,385 of 5,385 unique name matches picked the same athlete); (3) crew / team entries (sailing, rowing, relays) where the table lists the country, not athletes:
the crew's result is given to its members, only when the country has a single entry in that event and stage.
Sports whose result is not a mark (fencing bouts, judo wins, football goals) are not forced into result_value: their full tables stay in olympedia_round_results.   Usage: python scripts/fill_event_marks_from_rounds.py"""
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.viz.charts_sports import parse_value, unit_for  # noqa: E402

c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
MIN_TIME = 8.0
PLAIN = re.compile(r"^\d+(?::\d+){0,2}(?:[.,]\d+)?$")
HYPHEN = re.compile(r"^(\d+)-(\d{1,2}):(\d{2}(?:\.\d+)?)$")
HEAT = re.compile(r"heat\s*#?(\d+)", re.I)


def clean(text):
    """'55.2 (1)' -> '55.2'; '4-20:37' -> '4:20:37'; '10.0w (2.8 m/s)' -> '10.0'; gaps like 'at 0:00' and placeholders -> None."""
    t = str(text or "").strip()
    if not t or t.lower().startswith(("at ", "+", "same")) or t in ("–", "-"):
        return None
    t = t.split(" ")[0]
    m = HYPHEN.match(t)
    if m:
        t = f"{m.group(1)}:{m.group(2).zfill(2)}:{m.group(3)}"
    t = re.sub(r"[A-Za-z*]+$", "", t)
    if re.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", t):
        t = t.replace(",", "")
    if not PLAIN.match(t):
        return None
    return re.sub(r"^(\d+(?::\d+)*),(\d+)$", r"\1.\2", t)


def toks(s):
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch)).lower().replace("men's", "men").replace("women's", "women")
    return frozenset(re.findall(r"[a-z0-9]+", s))


def drop_toks(s):
    """names lost their accented letters in the warehouse ('Jos' for 'Jose'): compare with accented characters removed as well as folded"""
    return frozenset(re.findall(r"[a-z]{2,}", "".join(ch for ch in str(s or "").lower() if ord(ch) < 128)))


country_names = defaultdict(set)
for n, nm_ in c.execute("SELECT noc_code, historical_name FROM historical_nocs UNION SELECT iso_alpha3, country_name FROM countries"):
    if n and nm_:
        country_names[n].add(drop_toks(nm_))
for n, nm_ in c.execute("SELECT noc_code, country FROM athlete_participations WHERE country IS NOT NULL GROUP BY 1, 2"):
    country_names[n].add(drop_toks(nm_))


def is_country(noc, comp):
    """a crew / team entry names the country ('Denmark', 'Great Britain-1'); a person's name never equals it"""
    t = drop_toks(comp)
    return bool(t) and any(t == cn or (cn and cn <= t and len(t - cn) <= 1 and len(t) <= len(cn) + 1) for cn in country_names.get(noc, ()))


AUDIT = "--audit" in sys.argv   # compare what the method WOULD fill with rows that already hold a verified value; writes nothing

# ---------------------------------------------------------------- the round tables, indexed three ways
by_athlete = defaultdict(lambda: defaultdict(list))     # (games, sport, athlete id) -> event -> rows
team_rows = defaultdict(lambda: defaultdict(list))      # (games, sport, noc) -> event -> rows of country / crew entries (no athlete id)
names = defaultdict(list)                               # (games, sport, noc) -> [(folded words, dropped words, athlete id, event)]
for g, sp, ev, oid, noc, comp, sec, st, pint, mt, mh, ptxt, tix in c.execute("SELECT games_id, sport_name, event_name, athlete_id, noc, competitor, section, stage_rank, pos_int, mark_text, mark_header, pos_text, table_index FROM olympedia_round_results"):
    row = (sec, st * 1000 + min(tix, 999), pint, mt, mh, ptxt)   # stage first, then the later table within the same stage
    if oid:
        by_athlete[(g, sp, str(oid))][ev].append(row)
        if noc:
            names[(g, sp, noc)].append((toks(comp), drop_toks(comp), str(oid), ev))
    elif noc and is_country(noc, comp):
        team_rows[(g, sp, noc)][ev].append(row + (comp,))


def only_event(index):
    """the athlete's single MAIN event of that sport at those Games (sub-pages such as '- Race #1' or '- Run #2' do not count); None when there are several"""
    base = [n for n in index if " – " not in n and " - " not in n]
    return base[0] if len(base) == 1 else None


def pick_event(index, want):
    """exact event name first; otherwise the one event whose words contain (or are contained in) the requested event's words - never a guess between several"""
    if want in index:
        return want
    w = toks(want)
    hit = [name for name in index if w and (w <= toks(name) or toks(name) <= w)]
    if len(hit) > 1:   # sub-pages ('Four, Men - Run #1', a single lift) hold part of the result: prefer the event's own page
        main = [n for n in hit if " – " not in n and " - " not in n]
        eq = [n for n in main if {t for t in toks(n) if not t.isdigit()} == w]
        hit = eq if len(eq) == 1 else main if len(main) == 1 else hit
    return hit[0] if len(hit) == 1 else None


rows = c.execute("""SELECT e.result_id, e.games_id, s.sport_name, e.noc_code, a.full_name, e.event_name, m.oid, m.event, e.final_position, e.result_value, e.result_unit, e.heat, e.round, e.qualification_position
                    FROM event_results e JOIN sports s USING(sport_id) JOIN athletes a USING(athlete_id) LEFT JOIN event_result_olympedia_map m ON m.result_id=e.result_id
                    WHERE e.final_position IS NULL OR e.result_value IS NULL OR e.result_value='' OR e.round IS NULL OR {audit}""".format(audit='1=1' if AUDIT else '0=1')).fetchall()
audit = defaultdict(lambda: [0, 0])
ups = []
n_val = n_round = n_final = n_name = n_team = 0
for rid, g, sp, noc, name, ev_name, oid, mev, fpos, val, unit, heat, rnd, qpos in rows:
    sport_names = {sp, sp.replace("Equestrian", "Equestrianism")}
    want = mev or ev_name
    rs, how = None, None
    if oid:                                                  # (1) the linked Olympedia athlete
        for k in sport_names:
            idx_a = by_athlete.get((g, k, str(oid)), {})
            ev = pick_event(idx_a, want) or only_event(idx_a)
            if ev:
                rs, how = idx_a[ev], "id"
                break
    if rs is None and noc:                                   # (2) unique athlete by name + NOC + event words
        a, b = toks(name), drop_toks(name)
        hit = {(o, e) for k in sport_names for (tf, td, o, e) in names.get((g, k, noc), []) if (len(tf & a) >= 2 or len(td & b) >= 2) and (toks(ev_name) <= toks(e) or toks(e) <= toks(ev_name))}
        if not hit:   # event names differ between the sources (Sailing: "Men's One Person Dinghy" vs "One-Person Dinghy (Laser), Open"): accept the unique athlete if he / she has ONE main event in that sport and Games
            who = {o for k in sport_names for (tf, td, o, e) in names.get((g, k, noc), []) if len(tf & a) >= 2 or len(td & b) >= 2}
            if len(who) == 1:
                o = next(iter(who))
                for k in sport_names:
                    ev = only_event(by_athlete.get((g, k, o), {}))
                    if ev:
                        hit = {(o, ev)}
                        break
        if len({o for o, _ in hit}) == 1:
            o, e = sorted(hit)[0]
            for k in sport_names:
                if (g, k, o) in by_athlete and e in by_athlete[(g, k, o)]:
                    rs, how = by_athlete[(g, k, o)][e], "name"
                    break
    trs = None
    if noc:                                                  # (3) the country / crew entry of that event
        for k in sport_names:
            idx = team_rows.get((g, k, noc))
            if idx:
                ev = pick_event(idx, want)
                if ev:
                    trs = idx[ev]
                    break
    if not rs and not trs:
        continue
    new_val = new_unit = new_round = new_heat = new_q = new_final = None
    used = "athlete"
    # a crew entry counts only when the country has ONE entry at that stage
    team_ok = [r[:6] for r in (trs or []) if len({x[6] for x in trs if x[1] == r[1]}) == 1]
    for kind, pool in (("athlete", rs or []), ("team", team_ok)):
        if not pool:
            continue
        placed = sorted((r for r in pool if r[2] is not None and r[1] >= 1000), key=lambda r: (-r[1], r[2]))
        if placed and new_q is None and qpos is None:
            sec, st, pos = placed[0][0], placed[0][1], placed[0][2]
            new_round = sec if rnd is None else None
            new_q = pos
            hm = HEAT.search(sec or "")
            new_heat = hm.group(1) if hm and heat is None else None
            if fpos is None and st >= 100000:
                new_final = pos
        if (fpos is None or AUDIT) and new_final is None:    # the overall place printed in the event's main table
            overall = [r for r in pool if r[1] < 1000 and r[5] and re.fullmatch(r"=?\d+", str(r[5]).strip())]
            if len({r[5].lstrip("=") for r in overall}) == 1:
                new_final = int(overall[0][5].lstrip("="))
        if (val is None or val == "" or AUDIT) and new_val is None:
            for sec, st, pos, mt, mh, ptxt in sorted((r for r in pool if r[3]), key=lambda r: -r[1]):
                label, lower = unit_for(ev_name or want, mh)
                if label.startswith("Result as recorded"):
                    continue
                v = clean(mt)
                num = parse_value(v) if v else None
                if num is None or (lower and num < MIN_TIME):
                    continue
                new_val, used = v, kind
                new_unit = "seconds" if lower else "metres" if "Distance" in label else "kg" if "kg" in label else "points"
                break
    if AUDIT:
        key = (how or "-") + "/" + used
        if val and new_val:
            same = abs((parse_value(val) or -1) - (parse_value(new_val) or -2)) < 1e-6
            audit[key + " mark"][0] += same
            audit[key + " mark"][1] += 1
        if fpos is not None and new_final is not None:
            audit[key + " place"][0] += int(fpos) == int(new_final)
            audit[key + " place"][1] += 1
        continue
    if new_val or new_round or new_q or new_final:
        ups.append((new_final, new_val, new_unit if not unit else None, new_round, new_heat, new_q, rid))
        n_val += bool(new_val)
        n_round += bool(new_round)
        n_final += bool(new_final)
        n_name += how == "name"
        n_team += used == "team" and bool(new_val)
if AUDIT:
    for k, (ok, n) in sorted(audit.items()):
        print(f"AUDIT {k:22s} agrees with the verified value in {ok:,} of {n:,} rows ({100 * ok / max(n, 1):.1f}%)")
    sys.exit(0)
c.executemany("""UPDATE event_results SET final_position=COALESCE(final_position, ?), result_value=CASE WHEN (result_value IS NULL OR result_value='') AND ? IS NOT NULL THEN ? ELSE result_value END,
                 result_unit=COALESCE(result_unit, ?), round=COALESCE(round, ?), heat=COALESCE(heat, ?), qualification_position=COALESCE(qualification_position, ?) WHERE result_id=?""",
              [(a, b, b, u, rd, ht, q, rid) for a, b, u, rd, ht, q, rid in ups])
c.commit()
tot = c.execute("SELECT COUNT(*) FROM event_results").fetchone()[0]
q = lambda s: c.execute(s).fetchone()[0]
nv = q("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!=''")
npos = q("SELECT COUNT(final_position) FROM event_results")
print(f"filled: marks {n_val:,} (crew entries {n_team:,}), round/place {n_round:,}, overall places {n_final:,}; {n_name:,} rows matched by name+NOC+event (of {len(rows):,} candidate rows)")
print(f"event_results now: result_value {nv:,} ({100 * nv / tot:.0f}%) | final_position {npos:,} ({100 * npos / tot:.0f}%) | round {q('SELECT COUNT(round) FROM event_results'):,} | qualification_position {q('SELECT COUNT(qualification_position) FROM event_results'):,} of {tot:,}")
