#!/usr/bin/env python3
"""(1) Continent per NOC using IOC continental associations (static reference list; unified/neutral teams stay NULL).
(2) medals.is_shared from Olympedia positions: '=1' Gold / '=2' Silver with a medal = genuine tie. '=3' is NOT flagged because combat
sports award two bronzes by design (cannot be told apart from a tie without the rulebook). Offline, idempotent."""
import sqlite3
from pathlib import Path
c = sqlite3.connect(Path(__file__).resolve().parents[1]/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
M = {
 'Africa': 'ALG ANG BEN BOT BUR BDI CMR CPV CAF CHA COM CGO COD CIV DJI EGY GEQ ERI ETH GAB GAM GHA GUI GBS KEN LES LBR LBA MAD MAW MLI MTN MRI MAR MOZ NAM NIG NGR RWA STP SEN SEY SLE SOM RSA SSD SUD SWZ TAN TOG TUN UGA ZAM ZIM RHO UAR ZAI',
 'Americas': 'AHO ANT ARG ARU BAH BAR BIZ BER BOL BRA IVB CAN CAY CHI COL CRC CUB DMA DOM ECU ESA GRN GUA GUY HAI HON JAM MEX NCA PAN PAR PER PUR SKN LCA VIN SUR TTO URU USA VEN ISV WIF',
 'Asia': 'AFG BRN BAN BHU BRU CAM CHN HKG INA IND IRI IRQ JPN JOR KAZ PRK KOR KUW KGZ LAO LIB LBN MAS MDV MGL MYA NEP OMA PAK PLE PHI QAT KSA SGP SRI SYR TJK THA TLS TKM UAE UZB VIE VNM YEM TPE YAR YMD MAL COR',
 'Oceania': 'ASA AUS COK FIJ GUM KIR MHL FSM NRU NZL PLW PNG SAM SOL TGA TUV VAN',
 'Europe': 'ALB AND AUT BLR BEL BIH BUL CRO CYP CZE DEN EST FIN FRA GER GBR GRE HUN ISL IRL ISR ITA LAT LIE LTU LUX MLT MDA MON MNE NED MKD NOR POL POR ROU RUS SMR SRB SVK SLO ESP SWE SUI TUR UKR ARM AZE GEO KOS FRG GDR TCH URS YUG EUN ROC SCG'}
cont = {n: k for k, v in M.items() for n in v.split()}
for n, k in cont.items(): c.execute('UPDATE historical_nocs SET continent=? WHERE noc_code=?', (k, n))
c.execute('UPDATE countries SET continent=(SELECT continent FROM historical_nocs h WHERE h.historical_name=countries.country_name AND h.continent IS NOT NULL LIMIT 1) WHERE continent IS NULL')
print('NOCs without continent (neutral/unmapped):', [r[0] for r in c.execute('select noc_code from historical_nocs where continent is null')])
# shared medals
c.execute('UPDATE medals SET is_shared=0')
c.execute("""UPDATE medals SET is_shared=1 WHERE medal_id IN (
 SELECT m.medal_id FROM medals m JOIN athletes a ON a.athlete_id=m.athlete_id AND a.identity_key LIKE 'athlete_events:%'
 JOIN athlete_id_map im ON 'athlete_events:'||im.kaggle_id=a.identity_key
 JOIN olympedia_athlete_results r ON r.athlete_id=im.olympedia_athlete_id AND r.games_id=m.games_id
 WHERE r.medal=m.medal_type AND ((r.position='=1' AND m.medal_type='Gold') OR (r.position='=2' AND m.medal_type='Silver'))
 AND (SELECT COUNT(*) FROM medals m2 WHERE m2.athlete_id=m.athlete_id AND m2.games_id=m.games_id AND m2.medal_type=m.medal_type)=1)""")
c.commit()
q = lambda s: c.execute(s).fetchall()
print('continents', q('select continent,count(*) from historical_nocs group by 1'), 'countries w/ continent', q('select count(continent) from countries'))
print('shared medals', q('select medal_type,count(*) from medals where is_shared=1 group by 1'))
