# Visualization coverage report

Generated 2026-11-14 14:44 UTC by `scripts/build_viz_coverage.py`. Every chart is executed against the live warehouse (default filters, then Summer / Winter / since-2000 variants).

| Planned items | Implemented | Unavailable (missing data) | Pending | Registered charts | Extra charts |
|---|---|---|---|---|---|
| 106 | 106 | 0 | 0 | 111 | 0 |


## 1. Historical and time-series

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Line charts | ts_line_athletes | **implemented** |  |
| Multi-line comparison charts | ts_multi_index | **implemented** |  |
| Stacked area charts | ts_area_gender | **implemented** |  |
| Stream graphs | ts_stream_continent | **implemented** |  |
| Moving average charts | ts_moving_avg | **implemented** |  |
| Rolling trend charts | ts_rolling_trend | **implemented** |  |
| Step charts | ts_step_events | **implemented** |  |
| Slope charts | ts_slope_rank | **implemented** |  |
| Bump charts for changing country rankings | ts_bump_rank | **implemented** |  |
| Calendar-style historical activity charts | ts_calendar_activity | **implemented** |  |

## 2. Country and medal

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Horizontal medal ranking charts | c_rank_hbar | **implemented** |  |
| Grouped gold/silver/bronze bar charts | c_grouped_gsb | **implemented** |  |
| Stacked medal charts | c_stacked_gsb | **implemented** |  |
| Medal progression charts | c_progression | **implemented** |  |
| Medal share donut charts | c_share_donut | **implemented** |  |
| Medal distribution treemaps | c_treemap | **implemented** |  |
| Country comparison radar charts | c_radar | **implemented** |  |
| Medal efficiency scatter plots | c_efficiency | **implemented** |  |
| Medal concentration Lorenz curves | c_lorenz | **implemented** |  |
| Pareto charts | c_pareto | **implemented** |  |
| Country ranking heatmaps | c_rank_heatmap | **implemented** |  |
| Geographic choropleth maps | c_choropleth | **implemented** |  |
| Animated historical medal maps | c_map_animated | **implemented** |  |
| Country performance bubble charts | c_bubble | **implemented** |  |

## 3. Athlete

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Athlete age histograms | a_age_hist | **implemented** |  |
| Athlete age density plots | a_age_density | **implemented** |  |
| Box plots | a_box_age | **implemented** |  |
| Violin plots | a_violin_age | **implemented** |  |
| Athlete career timelines | a_career_timeline | **implemented** |  |
| Athlete medal progression charts | a_medal_progression | **implemented** |  |
| Athlete comparison radar charts | a_radar | **implemented** |  |
| Athlete performance scatter plots | a_scatter_careers | **implemented** |  |
| Athlete participation heatmaps | a_heat_participation | **implemented** |  |
| Athlete medal distribution charts | a_medal_distribution | **implemented** |  |
| Sankey diagrams for athlete career transitions | a_sankey_sports | **implemented** |  |

## 4. Sports and events

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Sports participation bar charts | s_participation_bar | **implemented** |  |
| Sports evolution timelines | s_evolution_timeline | **implemented** |  |
| Event count progression charts | s_event_progression | **implemented** |  |
| Sports popularity area charts | s_popularity_area | **implemented** |  |
| Sports medal heatmaps | s_medal_heatmap | **implemented** |  |
| Country-versus-sport heatmaps | s_country_sport_heatmap | **implemented** |  |
| Sport specialization bubble charts | s_specialization_bubble | **implemented** |  |
| Event result distribution charts | s_result_hist, s_result_decades | **implemented** |  |
| Record progression charts | s_record_progression | **implemented** |  |
| Olympic record versus world record comparisons | s_or_vs_wr | **implemented** |  |
| Gender participation by sport charts | s_gender_by_sport | **implemented** |  |

## 5. Statistical library

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Histograms | st_hist | **implemented** |  |
| KDE density plots | st_kde | **implemented** |  |
| ECDF plots | st_ecdf | **implemented** |  |
| Q-Q plots | st_qq | **implemented** |  |
| Box plots | st_box | **implemented** |  |
| Violin plots | st_violin | **implemented** |  |
| Strip plots | st_strip | **implemented** |  |
| Swarm plots | st_swarm | **implemented** |  |
| Scatter plots | st_scatter | **implemented** |  |
| Regression plots | st_regression | **implemented** |  |
| Residual plots | st_residual | **implemented** |  |
| Correlation heatmaps | st_corr_heatmap | **implemented** |  |
| Pair plots | st_pairplot | **implemented** |  |
| Confidence interval plots | st_ci_plot | **implemented** |  |
| Error bar charts | st_errorbar | **implemented** |  |
| Forest plots | st_forest | **implemented** |  |
| P-value comparison plots | st_pvalue | **implemented** |  |
| Effect size plots | st_effect | **implemented** |  |
| Distribution comparison plots | st_dist_compare | **implemented** |  |
| Outlier analysis plots | st_outliers | **implemented** |  |

## 6. Machine learning

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Actual versus predicted charts | ml_actual_pred | **implemented** |  |
| Prediction interval charts | ml_pred_interval | **implemented** |  |
| Residual distribution plots | ml_residual_dist | **implemented** |  |
| Feature importance charts | ml_feature_importance, ml_feature_importance_athlete, ml_shap_bar | **implemented** |  |
| SHAP summary plots | ml_shap_summary | **implemented** |  |
| SHAP dependence plots | ml_shap_dependence | **implemented** |  |
| ROC curves | ml_roc | **implemented** |  |
| Precision-recall curves | ml_pr | **implemented** |  |
| Confusion matrices | ml_confusion | **implemented** |  |
| Calibration curves | ml_calibration | **implemented** |  |
| Learning curves | ml_learning_curve | **implemented** |  |
| Cross-validation comparison charts | ml_cv_compare | **implemented** |  |
| K-Means cluster visualizations | ml_kmeans | **implemented** |  |
| Hierarchical clustering dendrograms | ml_dendrogram | **implemented** |  |
| PCA 2D and 3D projections | ml_pca2d, ml_pca3d | **implemented** |  |
| Elbow method charts | ml_elbow | **implemented** |  |
| Silhouette score charts | ml_silhouette | **implemented** |  |
| Model comparison dashboards | ml_model_dashboard | **implemented** |  |

## 7. Team sports

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| Tournament brackets | t_bracket | **implemented** |  |
| Knockout trees | t_knockout_tree | **implemented** |  |
| Group standings tables | t_standings | **implemented** |  |
| Match result timelines | t_match_timeline | **implemented** |  |
| Score progression charts | t_score_progression, t_scoring_by_period | **implemented** |  |
| Win/draw/loss distributions | t_wdl | **implemented** |  |
| Goal distribution charts | t_goal_dist | **implemented** |  |
| Team comparison radar charts | t_team_radar | **implemented** |  |
| Head-to-head comparison charts | t_h2h | **implemented** |  |
| Match score heatmaps | t_score_heatmap | **implemented** |  |
| Team performance progression | t_team_progression | **implemented** |  |
| Tournament journey visualizations | t_journey | **implemented** |  |

## 8. Data engineering

| Planned item | Chart(s) | Status | Note |
|---|---|---|---|
| ETL pipeline flow diagrams | de_etl_flow | **implemented** |  |
| Bronze/Silver/Gold record comparisons | de_medallion_compare | **implemented** |  |
| Data completeness heatmaps | de_completeness_heatmap | **implemented** |  |
| Missing data matrices | de_missing_matrix | **implemented** |  |
| Duplicate record charts | de_duplicates | **implemented** |  |
| Source coverage charts | de_source_coverage | **implemented** |  |
| Data quality scorecards | de_quality_scorecard | **implemented** |  |
| Pipeline execution timelines | de_pipeline_timeline | **implemented** |  |
| Scraping success/failure charts | de_scrape_status | **implemented** |  |
| Historical edition collection progress | de_edition_progress | **implemented** |  |

## Warnings

None.

## Filter-dependent availability

Charts that legitimately have no data under some filters (shown to users as a 'not available' state with the reason):

- `s_record_progression`: winter -> unavailable: no records for 100 metres, Men for this selection
- `s_or_vs_wr`: winter -> unavailable: no records for 100 metres, Men for this selection
- `t_wdl`: winter -> unavailable: no scored matches for this selection
- `t_goal_dist`: winter -> unavailable: no scored matches for this selection
- `t_team_radar`: winter -> unavailable: no scored matches for this selection
- `t_score_heatmap`: winter -> unavailable: no scored matches for this selection

## Data limitations that shape the implemented charts

- Event-result values: 74% of 263,893 result rows have a result value and 76% a final position; the event-result charts (`s_result_hist`, `s_result_decades`) therefore use the Olympedia main results tables (mostly finals), not every heat.
- Records: 160 events have record rows, from 8 disciplines only (archery, athletics, canoe sprint, modern pentathlon, rowing, short track, ski jumping, speed skating); swimming records are not in the source, so `s_record_progression` and `s_or_vs_wr` cover only those events.
- Fixture charts (team sports and head-to-head sports) use only sports with scored fixtures (>=100 matches): Tennis (2,092), Boxing (1,616), Basketball (1,173), Hockey (1,090), Volleyball (1,062), Curling (989), Taekwondo (950), Water Polo (938), Handball (902), Ice Hockey (840), Beach Volleyball (797), Archery (716), Football (716), Fencing (288), Baseball (208), Rugby Sevens (204), Basque pelota (168), Softball (145), Karate (139), 3x3 Basketball (136). Period scores are additive for basketball / water polo, cumulative for football / hockey / rugby sevens and set scores for volleyball / tennis, so score-progression charts are offered only for the first two groups.
- Knockout structure: fixtures carry stage labels only for medal matches ('Match 1/2', 'Match 3/4'); earlier rounds are reconstructed from dates (`t_bracket`, `t_knockout_tree`), and no official group tables exist (`t_standings` is one table per event).
- Data issue found and repaired: the Wikipedia football parser read kickoff times (e.g. 17:00) as scores and loaded each match from several pages on top of the Olympedia fixtures. 4,071 Wikipedia football rows (3,274 with a clock time as score) are archived in `archived_matches`; `matches` now holds the clean Olympedia football fixtures (0 clock-time scores remain). The parser is fixed and covered by a regression test.
- Athlete birth dates cover 70% of athletes; no chart depends on them (ages come from the age recorded at each Games).
- olympics.com refuses automated requests, so no chart uses it; the same facts come from Olympedia and Wikipedia.
- Correlation and regression charts treat NOC-Games observations as independent, which they are not (the same NOC repeats); the stored analyses use cluster-robust errors where it matters and say so.
