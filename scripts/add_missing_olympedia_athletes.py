#!/usr/bin/env python3
"""Athletes that appear in the scraped Olympedia results (olympedia_athlete_results) but not in the warehouse.  Offline, idempotent, nothing downloaded.
 1. A missing athlete that has exactly ONE look-alike warehouse athlete (same Games + NOC + sport, name tokens overlap) in all their results is the SAME person under
    another spelling -> linked in athlete_id_map (no new athlete created).
 2. An athlete with NO look-alike at all is genuinely missing -> added to athletes (name, gender, country) with their participations and event_results rows
    (event / place / medal / team from Olympedia).  Age is only filled when a birth year is known (olympedia_athlete_info).  Ambiguous ones (several look-alikes) are left out.
Rows created here: athletes.identity_key = 'olympedia:<id>', participations / results / events with source_url 'olympedia athlete results'."""
import collections
import difflib
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
NOW = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
SRC = "olympedia athlete results"


def q(sql, *args):
    return c.execute(sql, args).fetchall()


def toks(s):
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch)).lower()
    return frozenset(re.findall(r"[a-z]{2,}", s.replace("•", " ")))


def toks_drop(s):
    """Warehouse names lost their accented letters ('Jos' for 'Jose', 'Gutirrez'), so also compare with the accented characters removed instead of folded."""
    s = "".join(ch for ch in str(s or "").lower() if ord(ch) < 128)
    return frozenset(re.findall(r"[a-z]{2,}", s))


def etoks(s):
    s = (s or "").lower().replace("men's", "men").replace("women's", "women")
    return frozenset(re.findall(r"[a-z0-9½]+", s))


# ---- undo an earlier run so the stage is idempotent -----------------------------------------------------------------------------------------------
c.execute("CREATE TABLE IF NOT EXISTS athletes_added_missing (athlete_id INTEGER PRIMARY KEY)")
old = [r[0] for r in q("SELECT athlete_id FROM athletes_added_missing")]
for t in ("event_results", "athlete_participations", "events"):
    c.execute(f"DELETE FROM {t} WHERE source_url=?", (SRC,))
c.executemany("DELETE FROM athletes WHERE athlete_id=?", [(a,) for a in old])
c.execute("DELETE FROM athletes_added_missing")
c.execute("DELETE FROM athlete_id_map WHERE kaggle_id IN (SELECT kaggle_id FROM athlete_id_map_added)") if q("SELECT 1 FROM sqlite_master WHERE name='athlete_id_map_added'") else None
c.execute("CREATE TABLE IF NOT EXISTS athlete_id_map_added (kaggle_id TEXT PRIMARY KEY, olympedia_athlete_id TEXT)")
c.execute("DELETE FROM athlete_id_map WHERE kaggle_id IN (SELECT kaggle_id FROM athlete_id_map_added)")
c.execute("DELETE FROM athlete_id_map_added")
c.commit()

# ---- who is missing --------------------------------------------------------------------------------------------------------------------------------
miss = q("""WITH miss AS (SELECT DISTINCT CAST(athlete_id AS TEXT) oid FROM olympedia_athlete_results WHERE athlete_id IS NOT NULL
   AND CAST(athlete_id AS TEXT) NOT IN (SELECT olympedia_athlete_id FROM athlete_id_map)
   AND CAST(athlete_id AS TEXT) NOT IN (SELECT substr(identity_key,11) FROM athletes WHERE identity_key LIKE 'olympedia:%' AND athlete_id IN (SELECT athlete_id FROM athlete_participations)))
   SELECT r.athlete_id, r.athlete_name, r.noc, r.games_id, r.sport, r.event, r.position, r.team, r.medal, r.gender, r.country
   FROM olympedia_athlete_results r JOIN miss ON miss.oid=r.athlete_id""")
rows = collections.defaultdict(list)
for r in miss:
    rows[str(r[0])].append(r)
by = collections.defaultdict(list)
by_noc = collections.defaultdict(list)   # same Games + NOC, any sport (sport names differ between the sources)
for p in q("SELECT a.athlete_id, a.full_name, a.identity_key, p.noc_code, p.games_id, s.sport_name FROM athlete_participations p JOIN athletes a USING(athlete_id) JOIN sports s ON s.sport_id=p.sport_id"):   # base tables, not silver (silver may still hold rows from an earlier run)
    by[(p[4], p[3], p[5])].append((p[0], toks(p[1]), p[2]))
    by_noc[(p[4], p[3])].append((p[0], toks(p[1]), p[2]))
mapped_k = {r[0] for r in q("SELECT kaggle_id FROM athlete_id_map")}
links, new, ambiguous = {}, [], 0
amb_rows = []   # exported for a manual look: reports/athletes/ambiguous_olympedia_athletes.csv
names = dict(q("SELECT athlete_id, full_name FROM athletes"))
gender_of = dict(q("SELECT athlete_id, gender FROM athletes"))


def similarity(a, b):
    return difflib.SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
for oid, rs in rows.items():
    sets = []
    for r in rs:
        variants = [v for v in (toks(r[1]), toks_drop(r[1])) if v]
        same_sport = {a for a, t, k in by.get((r[3], r[2], r[4]), []) if t and any(len(t & n) >= 2 or (len(t & n) >= 1 and (t <= n or n <= t)) for n in variants)}
        any_sport = {a for a, t, k in by_noc.get((r[3], r[2]), []) if t and any(len(t & n) >= 2 or (len(t) >= 2 and t == n) for n in variants)}
        sets.append(same_sport | any_sport)
    inter, union = (set.intersection(*sets), set.union(*sets)) if sets else (set(), set())
    if not union:
        new.append(oid)
    elif len(inter) == 1 or len(union) == 1:
        links[oid] = next(iter(inter or union))
    else:
        # several look-alikes: accept the best only if it is clearly the closest name (and the sex agrees), otherwise leave the athlete out
        og = {"Men": "M", "Women": "F"}.get(rs[0][9])
        variants = [v for r in rs for v in (toks(r[1]), toks_drop(r[1])) if v]
        scored = sorted(((max(similarity(v, toks(names.get(a, ""))) for v in variants), a) for a in union if not og or gender_of.get(a) in (None, og)), reverse=True)
        if scored and scored[0][0] >= 0.75 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
            links[oid] = scored[0][1]
        else:
            ambiguous += 1
            for sc, a in scored[:5] or [(0, a) for a in sorted(union)[:5]]:
                amb_rows.append((oid, rs[0][1], rs[0][2], rs[0][3], rs[0][4], rs[0][9], a, names.get(a), round(sc, 3)))
ident = dict(q("SELECT athlete_id, identity_key FROM athletes"))
used = collections.Counter(links.values())
n_link = 0
for oid, a in links.items():
    k = ident.get(a, "")
    if used[a] == 1 and k.startswith("athlete_events:") and k[15:] not in mapped_k:
        c.execute("INSERT OR IGNORE INTO athlete_id_map(kaggle_id, olympedia_athlete_id) VALUES (?,?)", (k[15:], oid))
        c.execute("INSERT OR IGNORE INTO athlete_id_map_added VALUES (?,?)", (k[15:], oid))
        n_link += 1
c.commit()

# ---- add the genuinely missing athletes ------------------------------------------------------------------------------------------------------------
sports = {r[1]: r[0] for r in q("SELECT sport_id, sport_name FROM sports")}
sport_name = {v: k for k, v in sports.items()}
countries = {r[0]: r[1] for r in q("SELECT iso_alpha3, country_name FROM countries WHERE iso_alpha3 IS NOT NULL")}
countries.update({r[0]: r[1] for r in q("SELECT noc_code, historical_name FROM historical_nocs")})
ev_by = collections.defaultdict(list)
for eid, g, sid, name in q("SELECT event_id, games_id, sport_id, event_name FROM events"):
    ev_by[(g, sid)].append((eid, etoks(name) - etoks(sport_name.get(sid, "")), name))
age_info = {str(r[0]): r[1] for r in q("SELECT athlete_id, born FROM olympedia_athlete_info WHERE born IS NOT NULL")}
games_year = {r[0]: r[1] for r in q("SELECT games_id, year FROM games")}
n_ath = n_part = n_res = n_ev = n_skip = 0
seen = set()   # one row per athlete / Games / event (an Olympedia id listed with several NOCs for one event keeps the first)
for oid in new:
    rs = rows[oid]
    first = rs[0]
    gender = {"Men": "M", "Women": "F"}.get(first[9])
    ex = q("SELECT athlete_id FROM athletes WHERE identity_key=?", f"olympedia:{oid}")
    if ex:
        aid = ex[0][0]   # a bios-only athlete already exists for this Olympedia id: reuse it
        cur = None
    else:
      cur = c.execute("INSERT INTO athletes (full_name, gender, nationality, identity_key, source_url, verification_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (first[1], gender, first[10] or countries.get(first[2]), f"olympedia:{oid}", f"https://www.olympedia.org/athletes/{oid}", "collected", NOW, NOW))
      aid = cur.lastrowid
      c.execute("INSERT INTO athletes_added_missing VALUES (?)", (aid,))
    n_ath += 1
    born = re.search(r"(\d{4})", age_info.get(oid, "") or "")
    for r in rs:
        _, name, noc, g, sport, event, pos, team, medal, gen, country = r
        sid = sports.get(sport)
        if sid is None or g not in games_year:
            n_skip += 1
            continue
        T = etoks(event) - etoks(sport)
        hit = [e for e in ev_by[(g, sid)] if e[1] == T]
        if hit:   # an event can exist twice (CSV style "Rowing Men's Single Sculls" and Olympedia style "Single Sculls, Men"): prefer the CSV style, then the lowest id
            best = sorted(hit, key=lambda e: (not e[2].lower().startswith(sport.lower()), e[0]))[0]
            eid, ename = best[0], best[2]
        else:
            ename = f"{sport} {event}"
            eg = "F" if "women" in T else "M" if "men" in T else "X"
            eid = c.execute("INSERT INTO events (games_id, sport_id, event_name, event_gender, source_url, verification_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (g, sid, ename, eg, SRC, "collected", NOW, NOW)).lastrowid
            ev_by[(g, sid)].append((eid, T, ename))
            n_ev += 1
        if (aid, g, eid) in seen:
            continue
        seen.add((aid, g, eid))
        age = games_year[g] - int(born.group(1)) if born else None
        if age is not None and not 10 <= age <= 80:
            age = None   # same plausibility range as the rest of the warehouse
        med = medal if medal in ("Gold", "Silver", "Bronze") else None
        cp = c.execute("INSERT OR IGNORE INTO athlete_participations (athlete_id, games_id, sport_id, event_id, noc_code, country, team, age_at_competition, participation_status, medal, source_url, verification_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (aid, g, sid, eid, noc, countries.get(noc) or country, team, age, "competed", med, SRC, "collected", NOW, NOW))
        if cp.rowcount == 0:
            continue   # same athlete / Games / event / NOC listed twice
        n_part += 1
        m = re.match(r"^=?(\d+)$", str(pos or "").strip())
        st = re.match(r"^(DNF|DNS|DQ|AC|NM|NP|DSQ)\b", str(pos or "").strip())
        eg = "F" if "women" in etoks(event) else "M" if "men" in etoks(event) else "X"
        c.execute("INSERT INTO event_results (games_id, sport_id, event_id, event_name, event_gender, athlete_id, noc_code, final_position, medal, result_status, olympic_record, world_record, source_url, verification_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,0,0,?,?,?,?)",
                  (g, sid, eid, ename, eg, aid, noc, int(m.group(1)) if m else None, med, st.group(1) if st else "recorded", SRC, "collected", NOW, NOW))
        n_res += 1
c.commit()
print(f"missing athletes {len(rows):,}: linked to an existing athlete {n_link:,} | added as new {n_ath:,} (participations {n_part:,}, results {n_res:,}, new events {n_ev:,}, rows skipped {n_skip}) | ambiguous, left out {ambiguous}")

import csv
out = ROOT / "reports/athletes"
out.mkdir(parents=True, exist_ok=True)
with open(out / "ambiguous_olympedia_athletes.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["olympedia_id", "olympedia_name", "noc", "games_id", "sport", "sex", "candidate_athlete_id", "candidate_name", "name_similarity"])
    w.writerows(amb_rows)
with open(out / "bios_only_athletes_unlinked.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["athlete_id", "olympedia_id", "full_name", "gender", "nationality", "date_of_birth", "height_cm", "weight_kg"])
    w.writerows(q("SELECT athlete_id, substr(identity_key,11), full_name, gender, nationality, date_of_birth, height_cm, weight_kg FROM athletes WHERE identity_key LIKE 'olympedia:%' AND athlete_id NOT IN (SELECT DISTINCT athlete_id FROM athlete_participations) ORDER BY full_name"))
print("exported reports/athletes/ambiguous_olympedia_athletes.csv and bios_only_athletes_unlinked.csv")
