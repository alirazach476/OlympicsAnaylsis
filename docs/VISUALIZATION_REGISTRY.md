# Visualization registry

Generated 2026-11-14 14:44 UTC. 111 charts; served by `GET /api/viz/chart/{chart_id}` (JSON, or `?format=csv` for the data table). Registry: `GET /api/viz/registry`; coverage: `GET /api/viz/coverage`.

Common query filters: `season`, `year_from`, `year_to`, `noc` / `nocs`, `sport`, `games_id`, `event`, `athlete_ids`, `top`, `metric`, `a`, `b` (each chart honours only the filters listed for it).


## 1. Historical and time-series

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `ts_line_athletes` | overview | Athletes per Games | xy | Gold edition performance | `gold_edition_performance` | Show how Olympic participation has grown, Summer versus Winter | season year_range | `/api/viz/chart/ts_line_athletes` | implemented |
| `ts_multi_index` | overview | Growth of the Games (indexed) | xy | Gold edition performance | `gold_edition_performance` | Compare growth of athletes, NOCs, sports, events and medals on a common scale (first edition = 100) | season year_range | `/api/viz/chart/ts_multi_index` | implemented |
| `ts_area_gender` | overview | Male and female athletes per Games | xy | Gold edition performance | `gold_edition_performance` | Show the shift in gender composition of Olympic participation | season year_range | `/api/viz/chart/ts_area_gender` | implemented |
| `ts_stream_continent` | overview | Medal awards by continent (stream graph) | xy | Gold country medals x NOC continent | `gold_country_medals` | Show how the continental distribution of medals changed across Games | season year_range | `/api/viz/chart/ts_stream_continent` | implemented |
| `ts_moving_avg` | overview | Athletes with 3-edition moving average | xy | Gold edition performance | `gold_edition_performance` | Separate the long-run trend from edition-to-edition noise | season year_range | `/api/viz/chart/ts_moving_avg` | implemented |
| `ts_rolling_trend` | overview | Rolling trend in female share | xy | Gold edition performance | `gold_edition_performance` | Show whether the pace of gender-balance change is speeding up or slowing | year_range | `/api/viz/chart/ts_rolling_trend` | implemented |
| `ts_step_events` | overview | Events on the programme (step chart) | xy | Gold edition performance | `gold_edition_performance` | Show programme changes as discrete jumps between editions | season year_range | `/api/viz/chart/ts_step_events` | implemented |
| `ts_slope_rank` | overview | Slope chart: medals, first vs last Games in range | slope | Gold country medals | `gold_country_medals` | Show who gained or lost medal share between two editions | season year_range top | `/api/viz/chart/ts_slope_rank` | implemented |
| `ts_bump_rank` | overview | Bump chart: official medal-table rank | xy | Gold country medals | `gold_country_medals` | Show changing country rankings across Games | season year_range top nocs | `/api/viz/chart/ts_bump_rank` | implemented |
| `ts_calendar_activity` | editions | Competition-day activity calendar | calendar | Matches with dates | `matches` | Show on which days of each Games matches were played | season year_range | `/api/viz/chart/ts_calendar_activity` | implemented |

## 2. Country and medal

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `c_rank_hbar` | medals | Medal ranking (horizontal bars) | xy | Gold country medals | `gold_country_medals` | Rank nations by total medals in the selected window | season year_range top nocs | `/api/viz/chart/c_rank_hbar` | implemented |
| `c_grouped_gsb` | medals | Gold, silver and bronze by nation (grouped) | xy | Gold country medals | `gold_country_medals` | Compare medal composition of leading nations | season year_range top nocs | `/api/viz/chart/c_grouped_gsb` | implemented |
| `c_stacked_gsb` | medals | Medal composition (stacked) | xy | Gold country medals | `gold_country_medals` | Show total medals and their composition in one bar | season year_range top nocs | `/api/viz/chart/c_stacked_gsb` | implemented |
| `c_progression` | medals | Cumulative medal progression | xy | Gold country medals | `gold_country_medals` | Show how leading nations accumulated medals over the Games | season year_range nocs top | `/api/viz/chart/c_progression` | implemented |
| `c_share_donut` | medals | Medal share by nation (donut) | donut | Gold country medals | `gold_country_medals` | Show how concentrated medals are among the leaders | season year_range top | `/api/viz/chart/c_share_donut` | implemented |
| `c_treemap` | medals | Medal distribution treemap (continent, nation) | treemap | Gold country medals x historical NOCs | `gold_country_medals` | Show the hierarchy of medals from continent to nation | season year_range | `/api/viz/chart/c_treemap` | implemented |
| `c_radar` | countries | Country comparison radar | radar | ML clustering features / participation history | `gold_country_participation_history` | Compare the Olympic profile of several nations on common, normalised axes | nocs | `/api/viz/chart/c_radar` | implemented |
| `c_efficiency` | countries | Medal efficiency (athletes vs medals) | scatter | Gold country medals | `gold_country_medals` | Show which nations convert delegation size into medals most efficiently | season year_range | `/api/viz/chart/c_efficiency` | implemented |
| `c_lorenz` | medals | Medal concentration (Lorenz curve) | lorenz | Gold country medals x participation | `gold_country_medals` | Quantify how unequally medals are distributed across participating nations | season year_range | `/api/viz/chart/c_lorenz` | implemented |
| `c_pareto` | medals | Pareto chart of medals by nation | pareto | Gold country medals | `gold_country_medals` | Show the 80/20 pattern of medal winning | season year_range top | `/api/viz/chart/c_pareto` | implemented |
| `c_rank_heatmap` | countries | Country ranking heatmap | heatmap | Gold country medals | `gold_country_medals` | Show each leading nation's official rank at every Games at a glance | season year_range top | `/api/viz/chart/c_rank_heatmap` | implemented |
| `c_choropleth` | countries | Medals by country (choropleth) | map | Gold country medals x ISO codes | `gold_country_medals` | Show the geography of medal winning | season year_range | `/api/viz/chart/c_choropleth` | implemented |
| `c_map_animated` | countries | Animated historical medal map | map | Gold country medals x ISO codes | `gold_country_medals` | Show how the geography of accumulated medals evolved edition by edition | season year_range | `/api/viz/chart/c_map_animated` | implemented |
| `c_bubble` | countries | Country performance bubbles | scatter | Participation history | `gold_country_participation_history` | Relate delegation size, medal yield and total medals for every nation |  | `/api/viz/chart/c_bubble` | implemented |

## 3. Athlete

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `a_age_hist` | athletes | Athlete age histogram | xy | Silver participations | `silver_participations` | Show the age distribution of Olympic participants | season year_range sport noc | `/api/viz/chart/a_age_hist` | implemented |
| `a_age_density` | athletes | Age density: medalists vs other athletes | xy | Silver participations | `silver_participations` | Compare the age profile of medalists and non-medalists on a common density scale | season year_range sport noc | `/api/viz/chart/a_age_density` | implemented |
| `a_box_age` | athletes | Age by sport (box plots) | box | Silver participations | `silver_participations` | Compare age spread across sports | season year_range noc | `/api/viz/chart/a_box_age` | implemented |
| `a_violin_age` | athletes | Age distribution by season and gender (violin) | violin | Silver participations | `silver_participations` | Show the full shape of age distributions, not just quartiles | year_range sport noc | `/api/viz/chart/a_violin_age` | implemented |
| `a_career_timeline` | athletes | Athlete career timelines | timeline | Silver participations | `silver_participations` | Show when selected athletes competed and what they won | athlete_ids | `/api/viz/chart/a_career_timeline` | implemented |
| `a_medal_progression` | athletes | Athlete cumulative medal progression | xy | Gold athlete career x silver participations | `silver_participations` | Show how selected athletes accumulated medals Games by Games | athlete_ids | `/api/viz/chart/a_medal_progression` | implemented |
| `a_radar` | athletes | Athlete comparison radar | radar | Gold athlete career | `gold_athlete_career` | Compare selected athletes' careers on normalised axes | athlete_ids | `/api/viz/chart/a_radar` | implemented |
| `a_scatter_careers` | athletes | Career length vs medals (most decorated athletes) | scatter | Gold athlete career | `gold_athlete_career` | Relate longevity to success | season | `/api/viz/chart/a_scatter_careers` | implemented |
| `a_heat_participation` | athletes | Participation by age band and Games | heatmap | Silver participations | `silver_participations` | Show how the age mix of the Games has shifted | season year_range sport noc | `/api/viz/chart/a_heat_participation` | implemented |
| `a_medal_distribution` | athletes | How many medals do athletes win? | xy | Gold athlete career | `gold_athlete_career` | Show the heavy-tailed distribution of career medal counts |  | `/api/viz/chart/a_medal_distribution` | implemented |
| `a_sankey_sports` | athletes | Career transitions between sports (Sankey) | sankey | Silver participations | `silver_participations` | Show which sports athletes move between across consecutive Games | year_range | `/api/viz/chart/a_sankey_sports` | implemented |

## 4. Sports and events

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `s_participation_bar` | sports | Sports by number of participants | xy | Gold sport performance | `gold_sport_performance` | Show which sports attract the most athletes | season year_range top | `/api/viz/chart/s_participation_bar` | implemented |
| `s_evolution_timeline` | sports | Sports evolution timeline | timeline | Gold sport performance | `gold_sport_performance` | Show when each sport has been on the programme | season | `/api/viz/chart/s_evolution_timeline` | implemented |
| `s_event_progression` | sports | Event count progression by sport | xy | Gold sport performance | `gold_sport_performance` | Show which sports drove the growth of the programme | season year_range | `/api/viz/chart/s_event_progression` | implemented |
| `s_popularity_area` | sports | Sports popularity over time | xy | Gold sport performance | `gold_sport_performance` | Show the changing mix of athletes across sports | season year_range | `/api/viz/chart/s_popularity_area` | implemented |
| `s_medal_heatmap` | sports | Medal awards by sport and Games | heatmap | Gold sport performance | `gold_sport_performance` | Show where in the programme medals are decided | season year_range top | `/api/viz/chart/s_medal_heatmap` | implemented |
| `s_country_sport_heatmap` | sports | Country versus sport medal heatmap | heatmap | Medal table by sport | `medal_table_by_sport` | Reveal which nations dominate which sports | season year_range top | `/api/viz/chart/s_country_sport_heatmap` | implemented |
| `s_specialization_bubble` | sports | Sport specialization of nations | scatter | ML sport specialization | `analytics_results(ml/sport_specialization)` | Show whether nations win medals in many sports or concentrate in a few |  | `/api/viz/chart/s_specialization_bubble` | implemented |
| `s_result_hist` | sports | Distribution of results in an event | xy | Olympedia event rows | `olympedia_event_rows` | Show the spread of performances in one event across all Games | sport event | `/api/viz/chart/s_result_hist` | implemented |
| `s_result_decades` | sports | Results of an event by decade | box | Olympedia event rows | `olympedia_event_rows` | Show how performance in one event changed decade by decade | sport event | `/api/viz/chart/s_result_decades` | implemented |
| `s_record_progression` | records | Olympic record progression | xy | Gold records | `gold_records` | Show how the Olympic record in one event improved over the Games | event season | `/api/viz/chart/s_record_progression` | implemented |
| `s_or_vs_wr` | records | Olympic record versus world record | xy | Gold records | `gold_records` | Compare Olympic records with world records in the same event | event season | `/api/viz/chart/s_or_vs_wr` | implemented |
| `s_gender_by_sport` | sports | Gender participation by sport | xy | Gold gender participation | `gold_gender_participation` | Show how balanced each sport is between men and women | season year_range top | `/api/viz/chart/s_gender_by_sport` | implemented |

## 5. Statistical library

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `st_hist` | statistics | Histogram | xy | Stored distribution analysis | `analytics_results(stats/distributions)` | Show the frequency distribution of a variable | metric | `/api/viz/chart/st_hist` | implemented |
| `st_kde` | statistics | Kernel density estimate | xy | Stored distribution analysis | `analytics_results(stats/distributions)` | Show a smooth estimate of the distribution | metric | `/api/viz/chart/st_kde` | implemented |
| `st_ecdf` | statistics | Empirical cumulative distribution (ECDF) | xy | Stored distribution analysis | `analytics_results(stats/distributions)` | Read percentiles and compare distributions without binning | metric | `/api/viz/chart/st_ecdf` | implemented |
| `st_qq` | statistics | Q-Q plot against the normal distribution | scatter | Stored distribution analysis | `analytics_results(stats/distributions)` | Check how far a variable departs from normality | metric | `/api/viz/chart/st_qq` | implemented |
| `st_box` | statistics | Box plots of age: season and medal status | box | Silver participations | `silver_participations` | Compare age distributions across groups with robust summaries | year_range | `/api/viz/chart/st_box` | implemented |
| `st_violin` | statistics | Violin plots of age by season and medal status | violin | Stored distribution analysis | `analytics_results(stats/distributions)` | Show the full distribution shape per group |  | `/api/viz/chart/st_violin` | implemented |
| `st_strip` | statistics | Strip plot: age by sport (sample) | scatter | Silver participations | `silver_participations` | Show individual observations behind the summaries | year_range | `/api/viz/chart/st_strip` | implemented |
| `st_swarm` | statistics | Swarm plot: medalist age by season | scatter | Silver participations | `silver_participations` | Show every observation without overlap | year_range | `/api/viz/chart/st_swarm` | implemented |
| `st_scatter` | statistics | Scatter: delegation size vs medals | scatter | Gold country medals | `gold_country_medals` | Examine the relationship between two variables observation by observation | season year_range | `/api/viz/chart/st_scatter` | implemented |
| `st_regression` | statistics | Regression plot: log medals on log athletes | scatter | Gold country medals | `gold_country_medals` | Fit and display a simple regression with its uncertainty | season year_range | `/api/viz/chart/st_regression` | implemented |
| `st_residual` | statistics | Residuals vs fitted values | scatter | Stored regression diagnostics | `analytics_results(stats/regression)` | Check model assumptions: linearity and constant variance |  | `/api/viz/chart/st_residual` | implemented |
| `st_corr_heatmap` | statistics | Correlation heatmap | heatmap | Stored correlation analysis | `analytics_results(stats/correlations)` | Show pairwise associations between NOC-Games variables | metric | `/api/viz/chart/st_corr_heatmap` | implemented |
| `st_pairplot` | statistics | Pair plot of NOC-Games variables | pairs | Gold country medals | `gold_country_medals` | Inspect every pairwise relationship at once | season year_range | `/api/viz/chart/st_pairplot` | implemented |
| `st_ci_plot` | statistics | Confidence interval plot of the confirmatory tests | forest | Stored hypothesis tests | `analytics_hypothesis_tests` | Show each test's estimate and 95% interval on its own meaningful scale |  | `/api/viz/chart/st_ci_plot` | implemented |
| `st_errorbar` | statistics | Error bars: mean age with 95% CI | errorbar | Silver participations | `silver_participations` | Compare group means with their uncertainty | year_range | `/api/viz/chart/st_errorbar` | implemented |
| `st_forest` | statistics | Forest plot: Poisson regression rate ratios | forest | Stored regression models | `analytics_results(stats/regression)` | Show the multiplicative effect of each predictor on medal counts |  | `/api/viz/chart/st_forest` | implemented |
| `st_pvalue` | statistics | P-value comparison across tests | xy | Stored hypothesis tests | `analytics_hypothesis_tests` | Compare the strength of evidence across hypothesis tests on one scale |  | `/api/viz/chart/st_pvalue` | implemented |
| `st_effect` | statistics | Effect sizes of the tests | forest | Stored hypothesis tests | `analytics_hypothesis_tests` | Separate statistical significance from practical importance |  | `/api/viz/chart/st_effect` | implemented |
| `st_dist_compare` | statistics | Distribution comparison: Summer vs Winter athlete age | xy | Silver participations | `silver_participations` | Test visually and numerically whether two groups have the same distribution | year_range | `/api/viz/chart/st_dist_compare` | implemented |
| `st_outliers` | statistics | Outlier analysis: medals per NOC per Games | scatter | Gold country medals | `gold_country_medals` | Identify exceptional NOC-Games results with the 1.5 x IQR rule | year_range | `/api/viz/chart/st_outliers` | implemented |

## 6. Machine learning

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `ml_actual_pred` | machine-learning | Actual versus predicted medals | scatter | Medal prediction backtest | `analytics_results(ml/medal_prediction)` | Judge how close out-of-sample predictions are to reality |  | `/api/viz/chart/ml_actual_pred` | implemented |
| `ml_pred_interval` | machine-learning | Prediction intervals for one Games | interval | Medal prediction backtest | `analytics_results(ml/medal_prediction)` | Show predicted medals with an 80% interval against the actual result | games_id top | `/api/viz/chart/ml_pred_interval` | implemented |
| `ml_residual_dist` | machine-learning | Distribution of prediction residuals | xy | Medal prediction backtest | `analytics_results(ml/medal_prediction)` | Check whether prediction errors are centred and symmetric |  | `/api/viz/chart/ml_residual_dist` | implemented |
| `ml_feature_importance` | machine-learning | Feature importance: country medal model | xy | Medal prediction backtest | `analytics_results(ml/medal_prediction)` | Show which inputs drive country medal predictions |  | `/api/viz/chart/ml_feature_importance` | implemented |
| `ml_feature_importance_athlete` | machine-learning | Feature importance: athlete medal model | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Show which inputs drive an athlete's medal probability |  | `/api/viz/chart/ml_feature_importance_athlete` | implemented |
| `ml_shap_bar` | machine-learning | Mean absolute SHAP value per feature | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Rank features by their average impact on the XGBoost prediction |  | `/api/viz/chart/ml_shap_bar` | implemented |
| `ml_shap_summary` | machine-learning | SHAP summary (beeswarm) | beeswarm | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Show how feature values push individual predictions up or down |  | `/api/viz/chart/ml_shap_summary` | implemented |
| `ml_shap_dependence` | machine-learning | SHAP dependence plot | scatter | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Show how one feature's value changes its effect on the prediction | metric | `/api/viz/chart/ml_shap_dependence` | implemented |
| `ml_roc` | machine-learning | ROC curves | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Compare models' ability to rank medalists above non-medalists |  | `/api/viz/chart/ml_roc` | implemented |
| `ml_pr` | machine-learning | Precision-recall curves | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Compare models when positives (medalists) are rare |  | `/api/viz/chart/ml_pr` | implemented |
| `ml_confusion` | machine-learning | Confusion matrix | heatmap | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Show correct and incorrect classifications at the chosen decision threshold | metric | `/api/viz/chart/ml_confusion` | implemented |
| `ml_calibration` | machine-learning | Calibration curves | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Check whether predicted probabilities match observed frequencies |  | `/api/viz/chart/ml_calibration` | implemented |
| `ml_learning_curve` | machine-learning | Learning curve | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Diagnose whether more training data would help |  | `/api/viz/chart/ml_learning_curve` | implemented |
| `ml_cv_compare` | machine-learning | Cross-validation comparison across time folds | xy | Athlete medal model | `analytics_results(ml/athlete_medal_model)` | Compare models' stability over successive periods | metric | `/api/viz/chart/ml_cv_compare` | implemented |
| `ml_kmeans` | machine-learning | K-means clusters of nations | scatter | ML clustering | `analytics_results(ml/clustering)` | Show the groups of nations with similar Olympic profiles |  | `/api/viz/chart/ml_kmeans` | implemented |
| `ml_pca2d` | machine-learning | PCA projection (2D) | scatter | ML clustering | `analytics_results(ml/clustering)` | Reveal structure in the 8-dimensional country profile |  | `/api/viz/chart/ml_pca2d` | implemented |
| `ml_pca3d` | machine-learning | PCA projection (3D) | pca3d | ML clustering | `analytics_results(ml/clustering)` | Show a third principal component that the 2D view hides |  | `/api/viz/chart/ml_pca3d` | implemented |
| `ml_dendrogram` | machine-learning | Hierarchical clustering dendrogram | dendrogram | ML clustering | `analytics_results(ml/clustering)` | Show how nations merge into groups as the distance threshold grows |  | `/api/viz/chart/ml_dendrogram` | implemented |
| `ml_elbow` | machine-learning | Elbow method | xy | ML clustering | `analytics_results(ml/clustering)` | Judge the number of clusters from the drop in within-cluster variance |  | `/api/viz/chart/ml_elbow` | implemented |
| `ml_silhouette` | machine-learning | Silhouette score by number of clusters | xy | ML clustering | `analytics_results(ml/clustering)` | Choose the number of clusters by cluster separation |  | `/api/viz/chart/ml_silhouette` | implemented |
| `ml_model_dashboard` | machine-learning | Model comparison dashboard | scorecard | ML model registry | `analytics_results(ml/*)` | Summarise every model's validated performance in one place |  | `/api/viz/chart/ml_model_dashboard` | implemented |

## 7. Team sports

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `t_bracket` | team-sports | Tournament bracket (medal rounds) | bracket | Olympedia matches | `olympedia_matches` | Show how the finalists reached the medal matches | sport games_id event | `/api/viz/chart/t_bracket` | implemented |
| `t_knockout_tree` | team-sports | Knockout tree: the finalists' paths | tree | Olympedia matches | `olympedia_matches` | Trace each finalist back through its preceding matches | sport games_id event | `/api/viz/chart/t_knockout_tree` | implemented |
| `t_standings` | team-sports | Tournament standings table | table | Olympedia matches | `olympedia_matches` | Rank teams by results over one event | sport games_id event | `/api/viz/chart/t_standings` | implemented |
| `t_match_timeline` | team-sports | Match result timeline by team | timeline | Olympedia matches | `olympedia_matches` | Show each team's results across the days of the tournament | sport games_id event | `/api/viz/chart/t_match_timeline` | implemented |
| `t_score_progression` | team-sports | Score progression within a match | xy | Olympedia matches | `olympedia_matches` | Show how the score built up period by period in one match | sport games_id event | `/api/viz/chart/t_score_progression` | implemented |
| `t_scoring_by_period` | team-sports | Scoring by period across Games | xy | Olympedia matches | `olympedia_matches` | Show in which period most scoring happens and how that changed | sport | `/api/viz/chart/t_scoring_by_period` | implemented |
| `t_wdl` | team-sports | Win / draw / loss distribution | xy | Olympedia matches | `olympedia_matches` | Compare teams' results profile over all Games in the window | sport season year_range top | `/api/viz/chart/t_wdl` | implemented |
| `t_goal_dist` | team-sports | Distribution of goals per team per match | xy | Olympedia matches | `olympedia_matches` | Compare the scoring distribution with a Poisson model | sport season year_range | `/api/viz/chart/t_goal_dist` | implemented |
| `t_team_radar` | team-sports | Team comparison radar | radar | Olympedia matches | `olympedia_matches` | Compare teams on several performance dimensions | sport nocs season year_range | `/api/viz/chart/t_team_radar` | implemented |
| `t_h2h` | team-sports | Head-to-head record | xy | Olympedia matches | `olympedia_matches` | Compare two nations' direct results across the Games | sport a b | `/api/viz/chart/t_h2h` | implemented |
| `t_score_heatmap` | team-sports | Scoreline frequency heatmap | heatmap | Olympedia matches | `olympedia_matches` | Show which final scores occur most often | sport season year_range | `/api/viz/chart/t_score_heatmap` | implemented |
| `t_team_progression` | team-sports | Team performance progression | xy | Olympedia matches | `olympedia_matches` | Track one nation's results across successive Games | sport noc | `/api/viz/chart/t_team_progression` | implemented |
| `t_journey` | team-sports | Tournament journey of one team | xy | Olympedia matches | `olympedia_matches` | Follow one team's match-by-match margin and cumulative goal difference in a tournament | sport games_id event noc | `/api/viz/chart/t_journey` | implemented |

## 8. Data engineering

| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |
|---|---|---|---|---|---|---|---|---|---|
| `de_etl_flow` | engineering | ETL pipeline flow | flow | Warehouse tables | `sqlite_master + row counts` | Show how data moves from sources to the dashboard, with live record counts |  | `/api/viz/chart/de_etl_flow` | implemented |
| `de_medallion_compare` | engineering | Bronze / Silver / Gold record counts | xy | Warehouse tables | `src_* / silver_* / gold_*` | Show how record volume changes as data is cleaned and aggregated |  | `/api/viz/chart/de_medallion_compare` | implemented |
| `de_completeness_heatmap` | engineering | Data completeness heatmap | heatmap | Warehouse tables | `multiple (counts per Games)` | Show which data sets exist for which Games at a glance |  | `/api/viz/chart/de_completeness_heatmap` | implemented |
| `de_missing_matrix` | engineering | Missing-data matrix | heatmap | Silver participations x athletes x event results | `silver_participations, athletes, event_results` | Show which fields are incomplete, for which Games |  | `/api/viz/chart/de_missing_matrix` | implemented |
| `de_duplicates` | engineering | Duplicate records by entity | xy | Warehouse tables | `athlete_participations, event_results, matches, athletes` | Surface duplicated records so they can be reviewed |  | `/api/viz/chart/de_duplicates` | implemented |
| `de_source_coverage` | engineering | Source coverage by entity | xy | Warehouse tables | `athletes, matches, events, venues (source_url)` | Show which source each kind of record comes from |  | `/api/viz/chart/de_source_coverage` | implemented |
| `de_quality_scorecard` | engineering | Data quality scorecard | scorecard | Validation results | `reports/quality/validation_results.csv` | Show which automated data-quality checks pass |  | `/api/viz/chart/de_quality_scorecard` | implemented |
| `de_pipeline_timeline` | engineering | Pipeline execution timeline | timeline | Pipeline run log | `pipeline_runs` | Show when each pipeline stage ran, how long it took and whether it succeeded |  | `/api/viz/chart/de_pipeline_timeline` | implemented |
| `de_scrape_status` | engineering | Scraping success and failure | xy | Crawl queue and history | `crawl_queue, crawl_history, failed_pages.csv` | Show how much of the crawl succeeded, failed or is still pending |  | `/api/viz/chart/de_scrape_status` | implemented |
| `de_edition_progress` | engineering | Historical edition collection progress | xy | Warehouse tables | `multiple (counts per Games)` | Track how complete the collection is for every edition |  | `/api/viz/chart/de_edition_progress` | implemented |
