#!/usr/bin/env python3
"""NOC registry repair (idempotent; Bronze data untouched).

1. historical_nocs lacked three real IOC codes used by the official medal tables: EUA (United Team of Germany 1956-64), IOP (Independent Olympic
   Participants 1992), OAR (Olympic Athletes from Russia 2018). They are added as separate historical identities (never merged into successors).
2. ref_noc_alias maps source codes to the standard code per Games where the SOURCES disagree:
   * Wikipedia medal-table placeholders X_FOR/X_TAI (Formosa/Taiwan -> TPE), X_SIN (SGP), X_BRI (WIF), X_BER (BER), X_VIR (ISV), X_UZB (UZB), X_FRY (YUG)
   * CSV athlete data coded the 1960/64 United Team of Germany as GER and OAR 2018 as ROC; the medal tables use EUA / OAR.
   Every mapping carries a reason. X_UNK rows are not countries - they are the tables' 'Total' footer rows (handled in build_medallion).
"""
import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parents[1] / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
cols = [r[1] for r in c.execute("PRAGMA table_info(historical_nocs)")]
NEW = [
    ("EUA", "United Team of Germany", "Europe", 1, "United Team of Germany (East+West) 1956-1964; kept separate from GER/FRG/GDR", 1960, 1964),
    ("IOP", "Independent Olympic Participants", None, 1, "Independent Olympic Participants, 1992 (athletes from sanctioned/transitioning states)", 1992, 1992),
    ("OAR", "Olympic Athletes from Russia", "Europe", 1, "Neutral delegation at PyeongChang 2018 (ROC used from Tokyo 2020)", 2018, 2018),
]
for code, name, cont, neutral, note, y0, y1 in NEW:
    if not c.execute("SELECT 1 FROM historical_nocs WHERE noc_code=?", (code,)).fetchone():
        vals = {"noc_code": code, "historical_name": name, "continent": cont, "is_unified_or_neutral": neutral, "notes": note, "valid_from_year": y0, "valid_to_year": y1,
                "first_olympic_appearance": y0, "last_olympic_appearance": y1, "verification_status": "reference (IOC code list)",
                "created_at": "2026-11-13", "updated_at": "2026-11-13"}
        use = {k: v for k, v in vals.items() if k in cols}
        c.execute(f"INSERT INTO historical_nocs({','.join(use)}) VALUES ({','.join('?' * len(use))})", list(use.values()))
c.executescript("""DROP TABLE IF EXISTS ref_noc_alias;
CREATE TABLE ref_noc_alias(games_id TEXT, source TEXT, source_code TEXT, standard_code TEXT, reason TEXT, PRIMARY KEY(games_id, source, source_code));""")
rows = []
for g in ("1960_summer", "1960_winter", "1964_summer", "1964_winter"):
    rows.append((g, "athletes", "GER", "EUA", "United Team of Germany competed 1956-64; CSV data codes it GER"))
rows.append(("2018_winter", "athletes", "ROC", "OAR", "Olympic Athletes from Russia (OAR) in 2018; CSV data codes them ROC"))
ALIAS = {"X_FOR": ("TPE", "Formosa = Chinese Taipei"), "X_TAI": ("TPE", "Taiwan = Chinese Taipei"), "X_SIN": ("SGP", "Singapore"), "X_BRI": ("WIF", "British West Indies Federation"),
         "X_BER": ("BER", "Bermuda"), "X_VIR": ("ISV", "US Virgin Islands"), "X_UZB": ("UZB", "Uzbekistan"), "X_FRY": ("YUG", "FR Yugoslavia competed under the YUG code")}
for g in [r[0] for r in c.execute("SELECT games_id FROM games")]:
    for k, (std, why) in ALIAS.items():
        rows.append((g, "medal_table", k, std, why))
c.executemany("INSERT INTO ref_noc_alias VALUES (?,?,?,?,?)", rows)
c.commit()
print("registry rows now", c.execute("SELECT COUNT(*) FROM historical_nocs").fetchone()[0], "| aliases", len(rows))
