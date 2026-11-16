# Olympic Games 1960-2026: analysis of the complete dataset

Generated 2026-11-14 14:44 UTC by `scripts/build_analysis_report.py`; every number below is computed from the warehouse or a stored analysis at that moment. Charts for each finding are in the dashboard's Visualization Library (`/visualizations`).

## Key findings

- **The Games grew about 2.0x in athletes (Summer 5,702 in 1960 to 11,215 in 2024) and 1.8x in events**; Winter grew 4.4x (676 to 3,004).
- **Women went from 11.4% to 48.1% of Summer athletes** (Winter 21.9% to 46.2%); the linear trend is +2.6 share points per 4-year edition for Summer and +1.9 for Winter.
- **Medals are highly concentrated:** Gini 0.85 across participating NOCs; 27 nations account for 80% of all medals, and 73 of 230 nations that ever competed have never won one.
- **Hosting helps:** host nations won on average 12.5 more medals than in their other Games (Wilcoxon p = 0.0008, effect d = 0.58); 24 of 35 hosts beat their own non-host average.
- **Medalists are only marginally older** (+0.52 years; Cohen d = 0.09, negligible): age is statistically detectable but practically irrelevant.
- **Most athletes appear once** (70% compete at a single Games) and 74% of medalists won exactly one medal; the most decorated athlete is Michael Fred Phelps, II with 28 medals.
- **Past results already explain most of the future:** the best model (linear regression) reaches RMSE 3.40 medals vs 3.84 for simply repeating the previous Games (a modest gain); an athlete-level model reaches PR-AUC 0.32 against a base rate of 0.12.

## 1. The dataset

35 Games (17 Summer, 18 Winter), 263,893 athlete-event participations by 132,901 athletes from 231 NOCs across 78 sports and 6,547 event-editions (an event counted once per Games); 16,730 medal awards, 422,822 event-result rows, 15,311 scored fixtures, 96,392 team-roster entries, 1,647 venues and 1,531 record rows. Automated validation: 35 of 35 checks pass. All 35 editions pass every collection check (participations, results, verified medal table, fixtures, rosters, venues, Wikipedia pages, logo).

One defect found and repaired during this analysis: 4,071 Wikipedia football rows (kickoff times read as scores, duplicated across pages) were moved to `archived_matches`; Olympedia's clean fixtures are the single source for football. See the limitations section for what the data cannot support.

## 2. Growth and participation

| | First | Latest | Growth |
|---|---|---|---|
| Summer athletes | 5,702 (1960) | 11,215 (2024) | 1.97x |
| Summer events | 194 | 345 | 1.78x |
| Summer nations | 85 | 206 | 2.42x |
| Winter athletes | 676 (1960) | 3,004 (2026) | 4.44x |
| Winter events | 28 | 119 | 4.25x |
| Winter nations | 31 | 93 | 3.00x |

The largest Games by athletes is 2020 summer (11,868); the biggest single Summer jump between editions was 1988 (+1,831 athletes). Summer and Winter are different events with different scales, so they are analysed separately throughout.

**Gender.** Women's share of Summer athletes rose from 11.4% to 48.1%; it first reached 30% at 1996 summer and 40% at 2004 summer (Winter: 30% at 1994 winter). Both trends are strongly linear (R2 0.98 Summer), though residuals are autocorrelated, so the slope is a description, not a forecast.

## 3. Countries and medals

| Nation | Gold | Silver | Bronze | Total | Games attended |
|---|---|---|---|---|---|
| United States (USA) | 769 | 659 | 582 | 2,010 | 34 |
| Soviet Union (URS) | 406 | 312 | 296 | 1,014 | 15 |
| China (CHN) | 330 | 262 | 226 | 818 | 24 |
| Germany (GER) | 252 | 239 | 235 | 726 | 19 |
| Italy (ITA) | 198 | 181 | 240 | 619 | 35 |
| France (FRA) | 176 | 203 | 239 | 618 | 35 |
| Great Britain (GBR) | 182 | 191 | 224 | 597 | 35 |
| Japan (JPN) | 191 | 165 | 212 | 568 | 34 |
| Russia (RUS) | 192 | 163 | 184 | 539 | 13 |
| Australia (AUS) | 159 | 176 | 201 | 536 | 35 |

The ten leading NOCs hold 48.1% of all medals in the official tables (1960-2026; dissolved delegations such as the USSR and East Germany are ranked under their own codes). Concentration: Gini 0.85; 11 nations win half of all medals and 27 win 80%.

**Geography.** Continental share of medals, 1960s to 2010s: Europe 69% to 53%, Asia 6% to 19%, Americas 20% to 21%, Africa 2% to 3%, Oceania 4% to 4% (the rest is neutral or unassigned delegations).

**Biggest swings between consecutive Games** - gains: USA 1984 summer (+79); URS 1980 summer (+70); GDR 1972 summer (+41). Declines: USA 1988 summer (-79); URS 1988 summer (-64); CAN 1988 summer (-34).

**Summer vs Winter.** A medal-winning NOC takes a much larger share of the medal programme in Winter (median 10.5% of medal events per NOC-Games vs 1.7% in Summer; rank-biserial 0.60, large; Mann-Whitney p 3.1e-68), because far fewer nations win medals in a smaller programme. The share of participating NOCs that win a medal differs by season but only slightly (Cramer's V 0.06). Medal concentration (HHI) Summer 0.039, Winter 0.054.

## 4. Athletes

- Median age 24 (Summer) and 25 (Winter); 90% of participations fall between 18 and 35. Youngest medalist: Kokona Hiraki (11, Skateboarding, 2020 summer); oldest: Svetislav Pešić (74, Basketball, 2024 summer).
- Men and women medal at similar rates per participation (12.0% vs 13.5%); the association is statistically significant only because n is large (Cramer's V 0.021).
- 70% of athletes compete at one Games only; the longest careers are Ian Millar (10 Games); Afanasijs Kuzmins (9 Games); Hubert Raudaschl (9 Games).

Most decorated athletes (team-event medals count for every team member):

| Athlete | Gold | Silver | Bronze | Total | Games | Sports |
|---|---|---|---|---|---|---|
| Michael Fred Phelps, II | 23 | 3 | 2 | 28 | 5 | Swimming |
| Nikolay Yefimovich Andrianov | 7 | 5 | 3 | 15 | 3 | Gymnastics |
| Ole Einar Bjrndalen | 8 | 4 | 1 | 13 | 6 | Biathlon,Cross Country Skiing |
| Sawao Kato | 8 | 3 | 1 | 12 | 3 | Gymnastics |
| Birgit Fischer-Schmidt | 8 | 4 | 0 | 12 | 6 | Canoeing |
| Jennifer Elisabeth "Jenny" Thompson (-Cumpelik) | 8 | 3 | 1 | 12 | 4 | Swimming |
| Ryan Steven Lochte | 6 | 3 | 3 | 12 | 4 | Swimming |
| Larysa Semenivna Latynina (Diriy-) | 5 | 4 | 3 | 12 | 2 | Gymnastics |

Switching sport is rare: only about 1% of consecutive Games attendances involve a different sport, and the largest flows are Summer-to-Winter moves (e.g. Athletics to Bobsleigh) and neighbouring disciplines (cross-country skiing to biathlon).

## 5. Sports and events

- Largest sports by athlete entries: Athletics (28,748), Swimming (11,982), Rowing (8,925), Football (7,099), Cycling (7,023), Shooting (6,474).
- 46 sports first appear in this 1960-2026 data after 1960 (e.g. Bobsleigh, Baseball, Luge, Judo, Equestrian Eventing, Volleyball; some are returns of sports from earlier Games, such as Archery and Handball, or Winter sports absent from Squaw Valley 1960, such as Bobsleigh) and 18 have left the programme (Baseball, Karate, Softball, Equestrian Dressage, Basque pelota, Bowling, Artistic Gymnastics, Kendo, Canoe Slalom, Waterskiing, Roller Hockey, Cycling Mountain Bike, Trampolining, Cycling BMX Racing, Marathon Swimming, Wushu, Ice Stock Sport, Speed Skiing; not held at the latest Games).
- Gender balance at Paris 2024 (sports with 100+ athletes): most balanced near 50% women - Shooting 50%, Fencing 50%, Golf 50%; least female - Wrestling 33%, Equestrianism 36%, Football 41%.

**Olympic record progression** (best mark recorded at the first vs the latest Games with records; only events with 6+ record rows):

| Event | Years | First | Latest | Improvement |
|---|---|---|---|---|
| Hammer Throw, Men (summer) | 1960-1988 | 67.10 m | 84.80 m | 26.4% |
| 3,000 metres, Women (winter) | 1960-2026 | 314.30 s | 234.28 s | 25.5% |
| 1,000 metres, Women (winter) | 1960-2026 | 94.10 s | 72.31 s | 23.2% |
| 1,500 metres, Women (winter) | 1960-2022 | 145.20 s | 113.28 s | 22.0% |
| 5,000 metres, Men (winter) | 1964-2026 | 458.40 s | 363.95 s | 20.6% |
| 500 metres, Women (winter) | 1960-2026 | 45.90 s | 36.49 s | 20.5% |

Records come from 8 disciplines only (no swimming), and marks under different wind or timing conditions are not corrected.

## 6. Team sports (clean fixtures)

| Sport | Scored matches | Editions | Scoring per match, first vs latest Games | Trend per year | Mean draw rate | Best record (points per game) |
|---|---|---|---|---|---|---|
| Football | 716 | 17 | 4.29 (1960) to 2.97 (2024) goals | -0.016 (p = 0.015) | 20% | Soviet Union (2.46) |
| Basketball | 1,173 | 17 | 150.03 (1960) to 159.06 (2024) points | +0.111 (p = 0.394) | 0% | Argentina (1.98) |
| Ice Hockey | 840 | 18 | 11.13 (1960) to 5.41 (2026) goals | -0.072 (p = 0.000) | 6% | Soviet Union (2.49) |
| Handball | 902 | 14 | 32.45 (1972) to 55.67 (2024) goals | +0.439 (p = 0.000) | 5% | Unified Team (2.75) |
| Water Polo | 938 | 17 | 7.42 (1960) to 20.72 (2024) goals | +0.199 (p = 0.000) | 11% | Great Britain (2.46) |
| Hockey | 1,090 | 17 | 3.40 (1960) to 3.91 (2024) goals | +0.014 (p = 0.099) | 16% | Pakistan (2.13) |

Football goals per match by decade (both teams): 1960s 4.03 (89 matches, 18% draws), 1970s 3.30 (61 matches, 18% draws), 1980s 2.72 (96 matches, 22% draws), 1990s 2.88 (80 matches, 24% draws), 2000s 2.80 (158 matches, 16% draws), 2010s 2.72 (116 matches, 27% draws), 2020s 3.16 (116 matches, 18% draws).

Scoring in football fell from over four goals per match in the 1960s to roughly three, and has been stable since the 1990s; basketball and water polo scores are far higher and move with rule changes (shot clock, scoring format), so they are not comparable across sports.

## 7. What the models say

- **Country medal totals** (expanding-window backtest, 1,487 predictions): best model linear regression RMSE 3.40, MAE 1.47, R2 0.92; repeating the previous Games gives RMSE 3.84. The 80% prediction interval covers 88% of outcomes (nominal 80%, mean width 5.0 medals).
- **Athlete medal probability** (train < 2000, validate 2000-2007, test 2008-2026): random forest ROC-AUC 0.76, PR-AUC 0.32 (base rate 0.12). Strongest signals: sport_prior_rate, noc_prior_rate, prior_medals - i.e. the strength of the athlete's nation and sport, not athlete traits.
- **Country profiles:** k-means with k = 5 (silhouette 0.47, moderate separation) groups 218 NOCs by medal volume, medal efficiency, Winter share, specialisation and delegation size.

All modelling is retrospective validation on past Games; nothing here is a forecast of a future Games.

## 8. Limitations

- Event-result values: 74% of 263,893 result rows have a result value and 76% a final position; the event-result charts (`s_result_hist`, `s_result_decades`) therefore use the Olympedia main results tables (mostly finals), not every heat.
- Records: 160 events have record rows, from 8 disciplines only (archery, athletics, canoe sprint, modern pentathlon, rowing, short track, ski jumping, speed skating); swimming records are not in the source, so `s_record_progression` and `s_or_vs_wr` cover only those events.
- Fixture charts (team sports and head-to-head sports) use only sports with scored fixtures (>=100 matches): Tennis (2,092), Boxing (1,616), Basketball (1,173), Hockey (1,090), Volleyball (1,062), Curling (989), Taekwondo (950), Water Polo (938), Handball (902), Ice Hockey (840), Beach Volleyball (797), Archery (716), Football (716), Fencing (288), Baseball (208), Rugby Sevens (204), Basque pelota (168), Softball (145), Karate (139), 3x3 Basketball (136). Period scores are additive for basketball / water polo, cumulative for football / hockey / rugby sevens and set scores for volleyball / tennis, so score-progression charts are offered only for the first two groups.
- Knockout structure: fixtures carry stage labels only for medal matches ('Match 1/2', 'Match 3/4'); earlier rounds are reconstructed from dates (`t_bracket`, `t_knockout_tree`), and no official group tables exist (`t_standings` is one table per event).
- Data issue found and repaired: the Wikipedia football parser read kickoff times (e.g. 17:00) as scores and loaded each match from several pages on top of the Olympedia fixtures. 4,071 Wikipedia football rows (3,274 with a clock time as score) are archived in `archived_matches`; `matches` now holds the clean Olympedia football fixtures (0 clock-time scores remain). The parser is fixed and covered by a regression test.
- Athlete birth dates cover 70% of athletes; no chart depends on them (ages come from the age recorded at each Games).
- olympics.com refuses automated requests, so no chart uses it; the same facts come from Olympedia and Wikipedia.
- Correlation and regression charts treat NOC-Games observations as independent, which they are not (the same NOC repeats); the stored analyses use cluster-robust errors where it matters and say so.
- Medal counts follow the official tables (team medal = one per NOC); athlete-level medal counts credit every team member.
