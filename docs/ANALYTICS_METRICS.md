# Analytical metrics & methods

Every number on the dashboard is computed from the Gold/Silver layers by `scripts/build_medallion.py` (marts) and `scripts/run_analytics.py`
(statistics, sports modules, ML). Raw (Bronze) data is never modified. This file documents each metric so it can be reproduced.

## Source priority and data lineage
| Layer | Tables | Rule |
|---|---|---|
| Bronze | `src_*` (CSV folder), `olympedia_*`, `wikipedia_*`, `data/raw/**` | as collected, never overwritten |
| Silver | `silver_athletes`, `silver_participations`, `silver_medal_awards`, `silver_country_medals`, `silver_medal_table_totals` | cleaned, de-duplicated, NOC aliases applied (`ref_noc_alias`) |
| Gold | `gold_*` (12 marts + `gold_build_state`) | analytical marts, rebuilt per Games only when the Games' source fingerprint changes |

**Medal totals**: distinct Olympedia event podiums (`olympedia_podium_results`, parsed from the cached event pages; standings as fallback), team medals counted once
per event result and NOC. This reproduces official totals (Paris 2024 = 329 G / 330 S / 385 B). The Wikipedia medal tables are a *cross-check only*: about a quarter of
their rows are mis-parsed (tied ranks shift columns, footer "Total" rows appeared as a pseudo-country `X_UNK`, some person names parsed as countries).
`reconciliation_diff` = Olympedia total - Wikipedia total.

**NOC identity**: historical NOCs are never merged into successors. `ref_noc_alias` standardises only where sources disagree about the *same* team (CSV data codes the
1960/64 United Team of Germany as GER and OAR 2018 as ROC; Wikipedia used `X_FOR` etc. placeholders).

**Host NOC** (`ref_host_noc`): a documented reference fact (IOC host nation per Games), not collected data.

## Marts
| Mart | Grain | Key columns |
|---|---|---|
| gold_edition_performance | Games | athletes, nocs (excl. unknown), sports, events, medal_awards, female_share, mean_age |
| gold_country_medals | Games x NOC | gold/silver/bronze/total, tie-aware `official_rank`, gold_ratio, medal_share, is_host, wikipedia_total, reconciliation_diff |
| gold_athlete_career | athlete | games_count, career span, medals by colour, min/max age |
| gold_sport_performance | Games x sport | athletes, nocs, events, medal_awards, gender counts |
| gold_event_results | event finisher | position, medal, original result string + parsed value (`s` for times) - every finisher |
| gold_event_phases | round row | heats / semi-finals / pools of every event |
| gold_gender_participation | Games x sport x gender | athletes, medal participations |
| gold_host_performance | host edition | host medals vs previous / next / mean non-host editions |
| gold_team_sports | Games x team | played, W/D/L, GF/GA/GD, points per game |
| gold_records | record row | Olympic vs world level |
| gold_country_participation_history | NOC | appearances (Summer/Winter), athletes, medals, first medal |
| gold_athlete_age_performance | season x age band | participations, medalists, medal rate |
| gold_season_comparison | season | per-edition means and per-event / per-athlete medal rates |

## Statistics (`backend/analytics/stats.py`)
* **Descriptive**: mean, median, mode, min, max, range, variance, SD, quartiles, IQR, 5/10/90/95/99th percentiles, skewness (bias-corrected), excess kurtosis, CV.
* **Distributions**: histogram, Gaussian KDE, ECDF, normal Q-Q, Tukey box plot, violin (KDE), Pareto + Gini of medals across NOCs.
* **Correlation**: Pearson (+Fisher CI), Spearman, Kendall (sampled to 4,000 rows). Country-edition rows repeat NOCs, so p-values are optimistic. *Correlation is not causation.*
* **Hypothesis tests** (H1-H5, S1): H0/H1, test choice rationale, assumption checks, statistic, p, CI, effect size, interpretation. Family-wise **Holm** correction over the confirmatory family.
  H1 paired (host vs same NOC's non-host mean; Wilcoxon/paired t chosen by Shapiro-Wilk on the differences); H2 Mann-Whitney + Welch + bootstrap CI; H3 OLS trend per edition index + Spearman;
  H4a Mann-Whitney on medals per medal event, H4b chi-square (Cramér's V); H5 Kruskal-Wallis across decades + ANOVA + Tukey HSD.
* **Regression**: Poisson (cluster-robust), negative binomial (ML), OLS on log(1+medals) with HC3 + Breusch-Pagan + Durbin-Watson, logistic (odds ratios), within-NOC fixed-effects host model.
* **Time series**: observation index = Olympic edition; moving average, Holt smoothing, linear trend, one-change-point mean-shift (BIC), random-walk-with-drift ARIMA(0,1,0).
  With 17-18 observations per season, decomposition and SARIMA are **not** justified and are not reported.

## Machine learning (`backend/analytics/ml.py`) - historical backtests only
* **Country medal prediction**: expanding-window chronological backtest (10 test editions); all `prev_*` features come from earlier editions of the same season (unit-tested);
  `athletes`/`sports` are entry-list-time features (flagged). Models: naive baseline, linear, Poisson (log1p inputs), random forest, gradient boosting, XGBoost (count:poisson).
  Metrics MAE/RMSE/R²; 80% intervals from quantile boosting with empirical coverage reported.
* **Athlete medal probability**: train < 2000, validation 2000-2007 (threshold chosen here), test >= 2008. Features use only earlier Games. Precision, recall, F1, ROC-AUC, PR-AUC, Brier, confusion matrix, calibration.
* **Clustering**: K-Means (k by silhouette, k >= 3), Ward hierarchical (ARI agreement), DBSCAN cross-check, PCA projection. Clusters are described, not named.
* **Interpretability**: permutation importance, partial dependence, SHAP (tree models). Tracking in MLflow (`mlruns/`), artefacts in `models/`.

## Known limitations
* About 54% of athletes have no matched Olympedia profile (no birth date); `age` is available for 99.6% of participations.
* Result strings exist for every finisher of each event's final standings and its earlier rounds (`gold_event_results`, `gold_event_phases`); about half of the standings carry a numeric result (many events publish position only). Per-athlete finishes are available for athletes matched to an Olympedia profile.
* Records cover 8 disciplines (Olympedia); swimming records are not in the source.
* 10,094 participations have no NOC in the source (`UNK`); they are excluded from NOC counts.
* Medal reallocation notes: 328 medals carry a disqualification note from event-page prose; ~20% are loose context.
