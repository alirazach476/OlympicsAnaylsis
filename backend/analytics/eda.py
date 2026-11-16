"""PHASE 3 - exploratory analysis. Every result is computed from the Gold/Silver layers; findings text is generated from the numbers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .store import connect, save


def run(con) -> list[str]:
    q = lambda s: pd.read_sql(s, con)
    done = []

    # ---------- A. global overview
    ed = q("SELECT * FROM gold_edition_performance ORDER BY year, season")
    glob = {
        "editions": int(len(ed)), "summer_editions": int((ed.season == "summer").sum()), "winter_editions": int((ed.season == "winter").sum()),
        "participations": int(q("SELECT COUNT(*) n FROM silver_participations").n[0]), "unique_athletes": int(q("SELECT COUNT(DISTINCT athlete_id) n FROM silver_participations").n[0]),
        "nocs": int(q("SELECT COUNT(DISTINCT noc_code) n FROM silver_participations WHERE noc_code!='UNK'").n[0]), "sports": int(q("SELECT COUNT(DISTINCT sport_id) n FROM silver_participations").n[0]),
        "disciplines": int(q("SELECT COUNT(*) n FROM disciplines").n[0]), "events": int(q("SELECT COUNT(DISTINCT event_id) n FROM silver_participations").n[0]),
        "medal_awards": int(q("SELECT COUNT(*) n FROM silver_medal_awards").n[0]), "team_matches": int(q("SELECT COUNT(*) n FROM matches").n[0]),
        "participation_growth": ed[["games_id", "year", "season", "athletes", "nocs", "sports", "events"]],
    }
    for s in ("summer", "winter"):
        d = ed[ed.season == s].sort_values("year")
        glob[f"{s}_athlete_growth_first_to_last"] = round(float(d.athletes.iloc[-1] / d.athletes.iloc[0]), 2)
        glob[f"{s}_event_growth_first_to_last"] = round(float(d.events.iloc[-1] / d.events.iloc[0]), 2)
    save(con, "eda", "A_global_overview", "Global Olympic overview", glob, "How large is the Olympic programme and how has it grown since 1960?")
    done.append("A")

    # ---------- B. country performance
    cm = q("SELECT * FROM gold_country_medals")
    hist = q("SELECT * FROM gold_country_participation_history WHERE appearances>0")
    top = hist.sort_values(["gold", "total_medals"], ascending=False).head(25)
    first_medal = q("""SELECT noc_code, MIN(games_id) first_games FROM silver_country_medals WHERE total>0 GROUP BY noc_code""")
    firsts = (first_medal.merge(q("SELECT games_id, year FROM games"), left_on="first_games", right_on="games_id")
              .groupby("year").noc_code.apply(list).reset_index().sort_values("year"))
    never = hist[(hist.total_medals == 0)][["noc_code", "historical_name", "appearances", "athletes"]].sort_values("athletes", ascending=False)
    # medal growth/decline between consecutive editions of the same season
    cm = cm.sort_values(["season", "noc_code", "year"])
    cm["prev_total"] = cm.groupby(["season", "noc_code"]).total.shift(1)
    cm["delta"] = cm.total - cm.prev_total
    movers = cm.dropna(subset=["delta"]).sort_values("delta")
    sport_dom = q("""SELECT sport_name, noc_code, COUNT(*) medals FROM silver_medal_awards a GROUP BY 1,2""")
    sport_dom["share"] = sport_dom.medals / sport_dom.groupby("sport_name").medals.transform("sum")
    dom = sport_dom.sort_values("share", ascending=False).drop_duplicates("sport_name").sort_values("share", ascending=False).head(25)
    summ = cm.pivot_table(index="noc_code", columns="season", values="total", aggfunc="sum", fill_value=0).reset_index()
    nocs = q("SELECT noc_code, historical_name, is_unified_or_neutral, first_olympic_appearance, last_olympic_appearance FROM historical_nocs WHERE last_olympic_appearance IS NOT NULL AND last_olympic_appearance<2024 AND noc_code NOT IN ('AIN')")
    save(con, "eda", "B_country_performance", "Country performance", {
        "top_by_gold": top[["noc_code", "historical_name", "gold", "silver", "bronze", "total_medals", "appearances"]],
        "biggest_gains": movers.tail(10)[["games_id", "noc_code", "total", "prev_total", "delta"]], "biggest_declines": movers.head(10)[["games_id", "noc_code", "total", "prev_total", "delta"]],
        "first_time_medal_winners_by_year": firsts, "participants_without_a_medal": never.head(40), "participants_without_a_medal_count": int(len(never)),
        "sport_dominance_top": dom, "summer_vs_winter_total": summ.sort_values("summer", ascending=False).head(25),
        "historical_noc_transitions": nocs,
        "finding": f"{len(never)} of {len(hist)} NOCs that sent athletes have never appeared in an official medal table; the 10 leading NOCs hold "
                   f"{round(100 * top.head(10).total_medals.sum() / hist.total_medals.sum(), 1)}% of all medals awarded in the 35 Games.",
    }, "Which countries succeed, where, and how has that changed?")
    done.append("B")

    # ---------- C. athletes
    ath = q("SELECT * FROM gold_athlete_career")
    age = q("SELECT age, is_medalist, season FROM silver_participations WHERE age IS NOT NULL")
    ath_dec = ath.sort_values(["medals", "gold"], ascending=False).head(25)
    save(con, "eda", "C_athletes", "Athlete analysis", {
        "most_decorated": ath_dec[["athlete_id", "full_name", "gender", "gold", "silver", "bronze", "medals", "games_count", "nocs", "sports"]],
        "most_editions": ath.sort_values(["games_count", "medals"], ascending=False).head(15)[["athlete_id", "full_name", "games_count", "first_year", "last_year", "nocs", "sports"]],
        "longest_careers": ath.sort_values("career_span_years", ascending=False).head(15)[["athlete_id", "full_name", "career_span_years", "first_year", "last_year", "nocs", "sports"]],
        "multi_edition_medalists": int((ath.medal_games >= 2).sum()),
        "mean_age_medalist": round(float(age[age.is_medalist == 1].age.mean()), 2), "mean_age_non_medalist": round(float(age[age.is_medalist == 0].age.mean()), 2),
        "age_histogram": np.histogram(age.age, bins=range(10, 76, 2))[0].tolist(), "age_histogram_edges": list(range(10, 76, 2)),
        "gender_medal_participation": q("SELECT gender, COUNT(*) participations, SUM(is_medalist) medals FROM silver_participations WHERE gender IN ('M','F') GROUP BY gender"),
        "age_band_medal_rate": q("SELECT * FROM gold_athlete_age_performance ORDER BY season, age_band"),
    }, "Who are the most decorated athletes and how do age and careers relate to success?")
    done.append("C")

    # ---------- D. sports
    sp = q("SELECT * FROM sports WHERE first_appearance IS NOT NULL")
    gs = q("SELECT sport_name, season, COUNT(DISTINCT games_id) editions, SUM(athletes) athletes, MAX(events) max_events FROM gold_sport_performance GROUP BY sport_name, season")
    conc = q("SELECT sport_name, noc_code, COUNT(*) m FROM silver_medal_awards a GROUP BY 1,2")
    conc["share"] = conc.m / conc.groupby("sport_name").m.transform("sum")
    hhi = conc.groupby("sport_name").share.apply(lambda s: float((s ** 2).sum())).rename("medal_hhi").reset_index().sort_values("medal_hhi", ascending=False)
    save(con, "eda", "D_sports", "Sport analysis", {
        "popularity": gs.sort_values("athletes", ascending=False).head(25), "most_events": sp.sort_values("number_of_events", ascending=False).head(15)[["sport_name", "season", "number_of_events", "mens_events", "womens_events", "mixed_events"]],
        "introduced_after_1960": sp[sp.first_appearance > 1960][["sport_name", "season", "first_appearance"]].sort_values("first_appearance"),
        "discontinued": sp[sp.is_discontinued == 1][["sport_name", "season", "first_appearance", "last_appearance"]],
        "medal_concentration_hhi": hhi.head(20), "medal_concentration_hhi_note": "Herfindahl index of medal shares across NOCs: 1/n = perfectly spread, 1 = one NOC wins everything",
    }, "Which sports are large, new, discontinued or dominated by a few countries?")
    done.append("D")

    # ---------- E. gender
    ed["female_share_pct"] = (ed.female_share * 100).round(1)
    ms = {}
    for thr in (0.1, 0.2, 0.3, 0.4, 0.45):
        for s in ("summer", "winter"):
            d = ed[(ed.season == s) & (ed.female_share >= thr)].sort_values("year")
            ms[f"{s}_first_edition_at_or_above_{int(thr * 100)}pct"] = None if d.empty else d.games_id.iloc[0]
    ev = q("""SELECT g.season, g.year, SUM(e.event_gender IN ('M','Men')) men, SUM(e.event_gender IN ('F','Women')) women, SUM(e.event_gender IN ('X','Mixed')) mixed
              FROM events e JOIN games g ON g.games_id=e.games_id WHERE e.event_id IN (SELECT event_id FROM event_results) GROUP BY g.season, g.year ORDER BY g.year""")
    save(con, "eda", "E_gender", "Gender analysis", {
        "participation_by_edition": ed[["games_id", "year", "season", "male_athletes", "female_athletes", "female_share_pct"]], "event_counts_by_gender": ev, "milestones": ms,
        "by_sport_latest": q("""SELECT sport_name, season, SUM(CASE WHEN gender='F' THEN athletes END) f, SUM(CASE WHEN gender='M' THEN athletes END) m FROM gold_gender_participation
                                WHERE games_id IN ('2024_summer','2026_winter') GROUP BY sport_name, season"""),
        "medal_participation_by_gender": q("SELECT gender, COUNT(*) participations, SUM(is_medalist) medals, ROUND(1.0*SUM(is_medalist)/COUNT(*),4) rate FROM silver_participations WHERE gender IN ('M','F') GROUP BY gender"),
    }, "How has women's participation evolved?")
    done.append("E")

    # ---------- F. host
    hp = q("SELECT * FROM gold_host_performance ORDER BY year")
    hp["uplift_vs_prev"] = hp.host_medals - hp.prev_edition_medals
    hp["uplift_vs_mean_non_host"] = (hp.host_medals - hp.mean_non_host_medals).round(2)
    save(con, "eda", "F_host", "Host country analysis", {
        "rows": hp, "median_uplift_vs_prev": float(hp.uplift_vs_prev.median()), "hosts_that_beat_their_non_host_mean": int((hp.uplift_vs_mean_non_host > 0).sum()), "n_hosts": int(len(hp)),
        "note": "Host NOC per Games is a documented reference mapping (ref_host_noc). 'Non-host mean' = that NOC's mean total in other editions of the same season."}, "Do host countries win more?")
    done.append("F")

    # ---------- G. winter vs summer (normalised)
    sc = q("SELECT * FROM gold_season_comparison")
    norm = q("""SELECT season, ROUND(AVG(1.0*athletes/events),2) athletes_per_event, ROUND(AVG(1.0*medal_awards/events),3) medals_per_event, ROUND(AVG(1.0*nocs),1) nocs,
                ROUND(AVG(1.0*sports),1) sports FROM gold_edition_performance GROUP BY season""")
    conc2 = q("""SELECT g.season, a.noc_code, COUNT(*) m FROM silver_medal_awards a JOIN games g USING(games_id) GROUP BY 1,2""")
    conc2["share"] = conc2.m / conc2.groupby("season").m.transform("sum")
    save(con, "eda", "G_winter_vs_summer", "Winter vs Summer", {
        "season_totals": sc, "normalised_per_event": norm,
        "top_nocs_by_season": conc2.sort_values("share", ascending=False).groupby("season").head(10),
        "medal_hhi_by_season": conc2.groupby("season").share.apply(lambda s: float((s ** 2).sum())),
        "note": "Raw medal totals are NOT compared directly; per-event and per-athlete rates are shown because the two programmes differ in size.",
    }, "How do the two programmes compare once their different sizes are accounted for?")
    done.append("G")
    return done
