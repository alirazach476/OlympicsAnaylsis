#!/usr/bin/env python3
"""(1) ISO alpha-3 per NOC (IOC->ISO reference list for the codes that differ; historical/neutral delegations stay NULL).
(2) events.discipline_id: longest discipline name that prefixes the event name (same sport), else the sport's only discipline.
(3) disciplines first/last appearance from linked events. Offline, idempotent."""
import sqlite3
from pathlib import Path
c = sqlite3.connect(Path(__file__).resolve().parents[1]/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
DIFF = dict(ALG='DZA', ANG='AGO', ANT='ATG', ARU='ABW', ASA='ASM', BAH='BHS', BAN='BGD', BAR='BRB', BER='BMU', BHU='BTN', BIZ='BLZ', BOT='BWA', BRU='BRN', BRN='BHR',
 BUL='BGR', BUR='BFA', CAM='KHM', CAY='CYM', CGO='COG', CHA='TCD', CHI='CHL', CRC='CRI', CRO='HRV', DEN='DNK', ESA='SLV', FIJ='FJI', GAM='GMB', GBS='GNB', GER='DEU',
 GEQ='GNQ', GRE='GRC', GRN='GRD', GUA='GTM', GUI='GIN', HAI='HTI', HON='HND', INA='IDN', IRI='IRN', ISV='VIR', IVB='VGB', KSA='SAU', KUW='KWT', LAT='LVA', LBA='LBY',
 LES='LSO', LIB='LBN', LBN='LBN', MAD='MDG', MAS='MYS', MAW='MWI', MGL='MNG', MON='MCO', MRI='MUS', MTN='MRT', MYA='MMR', NCA='NIC', NED='NLD', NEP='NPL', NGR='NGA',
 NIG='NER', OMA='OMN', PAR='PRY', PHI='PHL', PLE='PSE', PUR='PRI', RSA='ZAF', SAM='WSM', SEY='SYC', SKN='KNA', SLO='SVN', SOL='SLB', SRI='LKA', SUD='SDN', SUI='CHE',
 TAN='TZA', TGA='TON', TOG='TGO', TPE='TWN', UAE='ARE', URU='URY', VAN='VUT', VIE='VNM', VIN='VCT', ZAM='ZMB', ZIM='ZWE', KOS='XKX')
SAME = 'AFG BDI CPV ALB AND ARG ARM AUS AUT AZE BEL BEN BIH BLR BOL BRA CAF CAN CHN CIV CMR COD COK COL COM CUB CYP CZE DJI DMA DOM ECU EGY ERI ESP EST ETH FIN FRA FSM GAB GBR GEO GHA GUM GUY HKG HUN IND IRL IRQ ISL ISR ITA JAM JOR JPN KAZ KEN KGZ KIR KOR LAO LBR LCA LIE LTU LUX MAR MDA MDV MEX MHL MKD MLI MLT MNE MOZ NAM NOR NRU NZL PAK PAN PER PLW PNG POL POR PRK QAT ROU RUS RWA SEN SGP SLE SMR SOM SRB SSD STP SUR SVK SWE SWZ SYR THA TJK TKM TLS TTO TUN TUR TUV UGA UKR USA UZB VEN YEM'.split()
iso = {**{k: k for k in SAME}, **DIFF}
c.execute('PRAGMA table_info(historical_nocs)')
if 'iso_alpha3' not in [r[1] for r in c.execute('PRAGMA table_info(historical_nocs)')]: c.execute('ALTER TABLE historical_nocs ADD COLUMN iso_alpha3 TEXT')
c.execute('UPDATE historical_nocs SET iso_alpha3=NULL')
for k, v in iso.items(): c.execute('UPDATE historical_nocs SET iso_alpha3=? WHERE noc_code=?', (v, k))
c.execute('UPDATE countries SET iso_alpha3=(SELECT iso_alpha3 FROM historical_nocs h WHERE h.historical_name=countries.country_name AND h.iso_alpha3 IS NOT NULL LIMIT 1) WHERE iso_alpha3 IS NULL')
# disciplines
c.execute('UPDATE events SET discipline_id=NULL')
discs = c.execute('SELECT discipline_id, sport_id, discipline_name, season FROM disciplines').fetchall()
by_sport = {}
for d in discs: by_sport.setdefault(d[1], []).append(d)
skipped = 0
for eid, sid, name in c.execute('SELECT event_id, sport_id, event_name FROM events').fetchall():
    cand = by_sport.get(sid, []); pick = None
    for d in sorted(cand, key=lambda d: -len(d[2])):
        if name.lower().startswith(d[2].lower() + ' '): pick = d[0]; break
    if pick is None and len(cand) == 1: pick = cand[0][0]
    if pick:
        try: c.execute('UPDATE events SET discipline_id=? WHERE event_id=?', (pick, eid))
        except sqlite3.IntegrityError: skipped += 1   # unique(games, discipline, name, gender) already taken by a near-duplicate event row
c.execute("""UPDATE disciplines SET first_appearance=(SELECT MIN(g.year) FROM events e JOIN games g ON g.games_id=e.games_id WHERE e.discipline_id=disciplines.discipline_id AND e.event_id IN (SELECT event_id FROM event_results)),
 last_appearance=(SELECT MAX(g.year) FROM events e JOIN games g ON g.games_id=e.games_id WHERE e.discipline_id=disciplines.discipline_id AND e.event_id IN (SELECT event_id FROM event_results))""")
c.commit(); print('skipped (duplicate-key)', skipped)
q = lambda s: c.execute(s).fetchall()
print('iso', q('select count(iso_alpha3),count(*) from historical_nocs'), 'countries', q('select count(iso_alpha3) from countries'), '| events w/ discipline', q('select count(discipline_id),count(*) from events'),
      '| disciplines w/ appearance', q('select count(first_appearance),count(*) from disciplines'))
print('unmapped NOCs', [r[0] for r in c.execute('select noc_code from historical_nocs where iso_alpha3 is null')])
