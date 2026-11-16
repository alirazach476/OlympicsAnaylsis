"""The planned visualization library: every item of the requirement, mapped to the chart builder(s) that implement it.
An item with no registered chart is reported as 'pending'; a chart whose builder raises Unavailable is 'unavailable (missing data)'."""

PLAN: list[tuple[int, str, tuple[str, ...]]] = [
    # 1 Historical and time-series
    (1, "Line charts", ("ts_line_athletes",)), (1, "Multi-line comparison charts", ("ts_multi_index",)), (1, "Stacked area charts", ("ts_area_gender",)),
    (1, "Stream graphs", ("ts_stream_continent",)), (1, "Moving average charts", ("ts_moving_avg",)), (1, "Rolling trend charts", ("ts_rolling_trend",)),
    (1, "Step charts", ("ts_step_events",)), (1, "Slope charts", ("ts_slope_rank",)), (1, "Bump charts for changing country rankings", ("ts_bump_rank",)),
    (1, "Calendar-style historical activity charts", ("ts_calendar_activity",)),
    # 2 Country and medal
    (2, "Horizontal medal ranking charts", ("c_rank_hbar",)), (2, "Grouped gold/silver/bronze bar charts", ("c_grouped_gsb",)), (2, "Stacked medal charts", ("c_stacked_gsb",)),
    (2, "Medal progression charts", ("c_progression",)), (2, "Medal share donut charts", ("c_share_donut",)), (2, "Medal distribution treemaps", ("c_treemap",)),
    (2, "Country comparison radar charts", ("c_radar",)), (2, "Medal efficiency scatter plots", ("c_efficiency",)), (2, "Medal concentration Lorenz curves", ("c_lorenz",)),
    (2, "Pareto charts", ("c_pareto",)), (2, "Country ranking heatmaps", ("c_rank_heatmap",)), (2, "Geographic choropleth maps", ("c_choropleth",)),
    (2, "Animated historical medal maps", ("c_map_animated",)), (2, "Country performance bubble charts", ("c_bubble",)),
    # 3 Athlete
    (3, "Athlete age histograms", ("a_age_hist",)), (3, "Athlete age density plots", ("a_age_density",)), (3, "Box plots", ("a_box_age",)), (3, "Violin plots", ("a_violin_age",)),
    (3, "Athlete career timelines", ("a_career_timeline",)), (3, "Athlete medal progression charts", ("a_medal_progression",)), (3, "Athlete comparison radar charts", ("a_radar",)),
    (3, "Athlete performance scatter plots", ("a_scatter_careers",)), (3, "Athlete participation heatmaps", ("a_heat_participation",)), (3, "Athlete medal distribution charts", ("a_medal_distribution",)),
    (3, "Sankey diagrams for athlete career transitions", ("a_sankey_sports",)),
    # 4 Sports and events
    (4, "Sports participation bar charts", ("s_participation_bar",)), (4, "Sports evolution timelines", ("s_evolution_timeline",)), (4, "Event count progression charts", ("s_event_progression",)),
    (4, "Sports popularity area charts", ("s_popularity_area",)), (4, "Sports medal heatmaps", ("s_medal_heatmap",)), (4, "Country-versus-sport heatmaps", ("s_country_sport_heatmap",)),
    (4, "Sport specialization bubble charts", ("s_specialization_bubble",)), (4, "Event result distribution charts", ("s_result_hist", "s_result_decades")),
    (4, "Record progression charts", ("s_record_progression",)), (4, "Olympic record versus world record comparisons", ("s_or_vs_wr",)), (4, "Gender participation by sport charts", ("s_gender_by_sport",)),
    # 5 Statistical
    (5, "Histograms", ("st_hist",)), (5, "KDE density plots", ("st_kde",)), (5, "ECDF plots", ("st_ecdf",)), (5, "Q-Q plots", ("st_qq",)), (5, "Box plots", ("st_box",)),
    (5, "Violin plots", ("st_violin",)), (5, "Strip plots", ("st_strip",)), (5, "Swarm plots", ("st_swarm",)), (5, "Scatter plots", ("st_scatter",)), (5, "Regression plots", ("st_regression",)),
    (5, "Residual plots", ("st_residual",)), (5, "Correlation heatmaps", ("st_corr_heatmap",)), (5, "Pair plots", ("st_pairplot",)), (5, "Confidence interval plots", ("st_ci_plot",)),
    (5, "Error bar charts", ("st_errorbar",)), (5, "Forest plots", ("st_forest",)), (5, "P-value comparison plots", ("st_pvalue",)), (5, "Effect size plots", ("st_effect",)),
    (5, "Distribution comparison plots", ("st_dist_compare",)), (5, "Outlier analysis plots", ("st_outliers",)),
    # 6 Machine learning
    (6, "Actual versus predicted charts", ("ml_actual_pred",)), (6, "Prediction interval charts", ("ml_pred_interval",)), (6, "Residual distribution plots", ("ml_residual_dist",)),
    (6, "Feature importance charts", ("ml_feature_importance", "ml_feature_importance_athlete", "ml_shap_bar")), (6, "SHAP summary plots", ("ml_shap_summary",)), (6, "SHAP dependence plots", ("ml_shap_dependence",)),
    (6, "ROC curves", ("ml_roc",)), (6, "Precision-recall curves", ("ml_pr",)), (6, "Confusion matrices", ("ml_confusion",)), (6, "Calibration curves", ("ml_calibration",)),
    (6, "Learning curves", ("ml_learning_curve",)), (6, "Cross-validation comparison charts", ("ml_cv_compare",)), (6, "K-Means cluster visualizations", ("ml_kmeans",)),
    (6, "Hierarchical clustering dendrograms", ("ml_dendrogram",)), (6, "PCA 2D and 3D projections", ("ml_pca2d", "ml_pca3d")), (6, "Elbow method charts", ("ml_elbow",)),
    (6, "Silhouette score charts", ("ml_silhouette",)), (6, "Model comparison dashboards", ("ml_model_dashboard",)),
    # 7 Team sports
    (7, "Tournament brackets", ("t_bracket",)), (7, "Knockout trees", ("t_knockout_tree",)), (7, "Group standings tables", ("t_standings",)), (7, "Match result timelines", ("t_match_timeline",)),
    (7, "Score progression charts", ("t_score_progression", "t_scoring_by_period")), (7, "Win/draw/loss distributions", ("t_wdl",)), (7, "Goal distribution charts", ("t_goal_dist",)),
    (7, "Team comparison radar charts", ("t_team_radar",)), (7, "Head-to-head comparison charts", ("t_h2h",)), (7, "Match score heatmaps", ("t_score_heatmap",)),
    (7, "Team performance progression", ("t_team_progression",)), (7, "Tournament journey visualizations", ("t_journey",)),
    # 8 Data engineering
    (8, "ETL pipeline flow diagrams", ("de_etl_flow",)), (8, "Bronze/Silver/Gold record comparisons", ("de_medallion_compare",)), (8, "Data completeness heatmaps", ("de_completeness_heatmap",)),
    (8, "Missing data matrices", ("de_missing_matrix",)), (8, "Duplicate record charts", ("de_duplicates",)), (8, "Source coverage charts", ("de_source_coverage",)),
    (8, "Data quality scorecards", ("de_quality_scorecard",)), (8, "Pipeline execution timelines", ("de_pipeline_timeline",)), (8, "Scraping success/failure charts", ("de_scrape_status",)),
    (8, "Historical edition collection progress", ("de_edition_progress",)),
]
