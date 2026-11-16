"""Load curated athlete_events CSV (Olympedia-derived) into the warehouse.

Source authority: third-party curated historical dataset (moderndive / Olympedia scrape).
Filter: Year >= 1960. Summer and Winter kept distinct via games_id.
Does not invent missing height/weight/age/medal values.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collectors.editions import all_editions, get_edition
from backend.models.core import (
    Athlete,
    AthleteParticipation,
    Country,
    Event,
    EventResult,
    Game,
    HistoricalNOC,
    Medal,
    MedalTable,
    Source,
    Sport,
)
from backend.scrapers.wikipedia.crawler import WikipediaOlympicsCrawler

logger = logging.getLogger(__name__)

SOURCE_NAME = "athlete_events_through_2026"
SOURCE_URL = (
    "https://github.com/ismayc/olympic-moderndive-data"
    " (athlete_events_through_2026.csv; Olympedia-derived)"
)


def _to_decimal(val) -> Optional[Decimal]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _clean_str(val) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s or None


def _medal(val) -> Optional[str]:
    m = _clean_str(val)
    if not m or m.lower() in {"na", "nan", "none"}:
        return None
    return m.title()


def _games_id(year: int, season: str) -> str:
    return f"{int(year)}_{season.strip().lower()}"


class AthleteEventsLoader:
    def __init__(self, session: Session, csv_path: Path):
        self.session = session
        self.csv_path = Path(csv_path)

    def ensure_source(self) -> Source:
        src = self.session.scalar(select(Source).where(Source.name == SOURCE_NAME))
        if src:
            return src
        src = Source(
            name=SOURCE_NAME,
            base_url=SOURCE_URL,
            license="See upstream repository / Olympedia terms",
            authority_rank=40,
            notes="Curated athlete-event rows; reconcile against official medal tables.",
        )
        self.session.add(src)
        self.session.flush()
        return src

    def ensure_games(self) -> None:
        WikipediaOlympicsCrawler(self.session).ensure_games_rows(all_editions())

    def load(self, *, min_year: int = 1960, max_year: int = 2026) -> dict:
        if not self.csv_path.exists():
            raise FileNotFoundError(self.csv_path)

        logger.info("Reading %s", self.csv_path)
        df = pd.read_csv(self.csv_path)
        # normalize column names
        df.columns = [c.strip() for c in df.columns]
        rename = {c: c[:1].upper() + c[1:] if c.islower() else c for c in df.columns}
        # expected Title Case from moderndive file
        df = df.rename(
            columns={
                "id": "ID",
                "name": "Name",
                "sex": "Sex",
                "age": "Age",
                "height": "Height",
                "weight": "Weight",
                "team": "Team",
                "noc": "NOC",
                "games": "Games",
                "year": "Year",
                "season": "Season",
                "city": "City",
                "sport": "Sport",
                "event": "Event",
                "medal": "Medal",
            }
        )

        df = df[(df["Year"] >= min_year) & (df["Year"] <= max_year)].copy()
        # Keep only editions in our registry (no invented summer 2026)
        valid_ids = {e.games_id for e in all_editions()}
        df["games_id"] = df.apply(lambda r: _games_id(r["Year"], r["Season"]), axis=1)
        df = df[df["games_id"].isin(valid_ids)].copy()
        logger.info("Rows after 1960–2026 edition filter: %s", len(df))

        self.ensure_source()
        self.ensure_games()

        sports_map: Dict[str, int] = {}
        events_map: Dict[Tuple[str, str, Optional[str]], int] = {}
        athletes_map: Dict[str, int] = {}
        noc_seen: Dict[str, str] = {}

        # Countries / NOCs
        for noc, team in (
            df[["NOC", "Team"]].dropna().drop_duplicates().itertuples(index=False, name=None)
        ):
            noc = str(noc).strip().upper()
            team_name = str(team).strip()
            if noc in noc_seen:
                continue
            noc_seen[noc] = team_name
            existing = self.session.scalar(
                select(HistoricalNOC).where(HistoricalNOC.noc_code == noc).limit(1)
            )
            if not existing:
                self.session.add(
                    HistoricalNOC(
                        noc_code=noc,
                        historical_name=team_name,
                        verification_status="collected",
                    )
                )
            country = self.session.scalar(
                select(Country).where(Country.country_name == team_name)
            )
            if not country:
                # Prefer NOC-level name without digits suffix quirks later
                self.session.add(
                    Country(
                        country_name=team_name,
                        current_country_name=team_name,
                        verification_status="collected",
                    )
                )
        self.session.flush()

        # Sports
        for sport_name in sorted(df["Sport"].dropna().unique()):
            sport_name = str(sport_name).strip()
            sport = self.session.scalar(select(Sport).where(Sport.sport_name == sport_name))
            if not sport:
                sport = Sport(
                    sport_name=sport_name,
                    source_url=SOURCE_URL,
                    verification_status="collected",
                )
                self.session.add(sport)
                self.session.flush()
            sports_map[sport_name] = sport.sport_id
        self.session.flush()

        # Athletes (unique by source ID)
        athlete_rows = df[["ID", "Name", "Sex", "Height", "Weight"]].drop_duplicates("ID")
        logger.info("Unique athletes in range: %s", len(athlete_rows))
        existing_keys = {
            k: aid
            for k, aid in self.session.execute(
                select(Athlete.identity_key, Athlete.athlete_id)
            ).all()
            if k and str(k).startswith("athlete_events:")
        }
        new_athletes = []
        pending_ids = []
        for row in athlete_rows.itertuples(index=False):
            src_id = str(int(row.ID))
            identity_key = f"athlete_events:{src_id}"
            if identity_key in existing_keys:
                athletes_map[src_id] = existing_keys[identity_key]
                continue
            new_athletes.append(
                Athlete(
                    full_name=str(row.Name).strip(),
                    gender=_clean_str(row.Sex),
                    height_cm=_to_decimal(row.Height),
                    weight_kg=_to_decimal(row.Weight),
                    identity_key=identity_key,
                    source_url=SOURCE_URL,
                    verification_status="collected",
                )
            )
            pending_ids.append(src_id)
            if len(new_athletes) >= 2000:
                self.session.add_all(new_athletes)
                self.session.flush()
                for sid, ath in zip(pending_ids, new_athletes):
                    athletes_map[sid] = ath.athlete_id
                new_athletes, pending_ids = [], []
                self.session.commit()
        if new_athletes:
            self.session.add_all(new_athletes)
            self.session.flush()
            for sid, ath in zip(pending_ids, new_athletes):
                athletes_map[sid] = ath.athlete_id
            self.session.commit()
        logger.info("Athletes loaded: %s", len(athletes_map))

        # Deduplicate exact athlete-event rows before insert
        df = df.drop_duplicates(
            subset=["ID", "games_id", "Event", "NOC", "Medal"], keep="first"
        )

        # Pre-create events
        event_defs = df[["games_id", "Sport", "Event"]].drop_duplicates()
        for erow in event_defs.itertuples(index=False):
            games_id = erow.games_id
            sport_name = str(erow.Sport).strip()
            event_name = str(erow.Event).strip()
            sport_id = sports_map.get(sport_name)
            el = event_name.lower()
            gender = "F" if "women" in el else ("M" if ("men" in el and "women" not in el) else ("X" if "mixed" in el else None))
            ev_key = (games_id, event_name, gender)
            if ev_key in events_map:
                continue
            existing_ev = self.session.scalar(
                select(Event).where(
                    Event.games_id == games_id,
                    Event.event_name == event_name,
                )
            )
            if existing_ev:
                events_map[ev_key] = existing_ev.event_id
            else:
                ev = Event(
                    games_id=games_id,
                    sport_id=sport_id,
                    event_name=event_name,
                    event_gender=gender,
                    source_url=SOURCE_URL,
                    verification_status="collected",
                )
                self.session.add(ev)
                self.session.flush()
                events_map[ev_key] = ev.event_id
        self.session.commit()
        logger.info("Events ready: %s", len(events_map))

        # Resolve event_id helper using gender inference
        def event_id_for(games_id: str, event_name: str) -> int:
            el = event_name.lower()
            gender = "F" if "women" in el else ("M" if ("men" in el and "women" not in el) else ("X" if "mixed" in el else None))
            return events_map[(games_id, event_name, gender)]

        part_buf = []
        result_buf = []
        medal_buf = []
        participations = 0
        medals = 0
        results = 0

        for i, row in enumerate(df.itertuples(index=False), start=1):
            games_id = row.games_id
            sport_name = str(row.Sport).strip()
            event_name = str(row.Event).strip()
            sport_id = sports_map.get(sport_name)
            event_id = event_id_for(games_id, event_name)
            athlete_id = athletes_map[str(int(row.ID))]
            noc = _clean_str(row.NOC)
            medal = _medal(row.Medal)
            el = event_name.lower()
            gender = "F" if "women" in el else ("M" if ("men" in el and "women" not in el) else ("X" if "mixed" in el else None))
            age = None
            if row.Age is not None and not (isinstance(row.Age, float) and pd.isna(row.Age)):
                try:
                    age = int(float(row.Age))
                except (TypeError, ValueError):
                    age = None

            part_buf.append(
                dict(
                    athlete_id=athlete_id,
                    games_id=games_id,
                    sport_id=sport_id,
                    event_id=event_id,
                    noc_code=noc,
                    country=_clean_str(row.Team),
                    team=_clean_str(row.Team),
                    age_at_competition=age,
                    participation_status="competed",
                    medal=medal,
                    source_url=SOURCE_URL,
                    verification_status="collected",
                )
            )
            result_buf.append(
                dict(
                    games_id=games_id,
                    sport_id=sport_id,
                    event_id=event_id,
                    event_name=event_name,
                    event_gender=gender,
                    athlete_id=athlete_id,
                    noc_code=noc,
                    medal=medal,
                    result_status="recorded",
                    source_url=SOURCE_URL,
                    verification_status="collected",
                    olympic_record=False,
                    world_record=False,
                )
            )
            if medal:
                medal_buf.append(
                    dict(
                        games_id=games_id,
                        event_id=event_id,
                        athlete_id=athlete_id,
                        noc_code=noc,
                        medal_type=medal,
                        is_shared=False,
                        is_team_medal=False,
                        source_url=SOURCE_URL,
                        verification_status="collected",
                    )
                )

            if len(part_buf) >= 2000:
                self.session.bulk_insert_mappings(AthleteParticipation, part_buf)
                self.session.bulk_insert_mappings(EventResult, result_buf)
                if medal_buf:
                    self.session.bulk_insert_mappings(Medal, medal_buf)
                participations += len(part_buf)
                results += len(result_buf)
                medals += len(medal_buf)
                part_buf, result_buf, medal_buf = [], [], []
                self.session.commit()
                logger.info("Progress i=%s participations=%s", i, participations)

        if part_buf:
            self.session.bulk_insert_mappings(AthleteParticipation, part_buf)
            self.session.bulk_insert_mappings(EventResult, result_buf)
            if medal_buf:
                self.session.bulk_insert_mappings(Medal, medal_buf)
            participations += len(part_buf)
            results += len(result_buf)
            medals += len(medal_buf)
            self.session.commit()

        medal_table_rows = self._build_medal_tables(df)
        self._enrich_games_counts(df)
        self.session.commit()

        summary = {
            "source": SOURCE_NAME,
            "csv": str(self.csv_path),
            "rows_loaded": int(len(df)),
            "athletes": len(athletes_map),
            "sports": len(sports_map),
            "events": len(events_map),
            "participations": participations,
            "results": results,
            "medals": medals,
            "medal_table_rows": medal_table_rows,
            "nocs": len(noc_seen),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "verification_status": "collected",
            "notes": (
                "Loaded from curated Olympedia-derived CSV. "
                "Not marked verified against olympics.com official standings."
            ),
        }
        out = Path("reports/scraping/historical_dataset_load.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Load complete: %s", summary)
        return summary

    def _build_medal_tables(self, df: pd.DataFrame) -> int:
        """Aggregate athlete-level medals to NOC tables (not official IOC rules for ties)."""
        medals = df[df["Medal"].notna()].copy()
        if medals.empty:
            return 0
        medals["Medal"] = medals["Medal"].map(_medal)
        medals = medals[medals["Medal"].notna()]
        medals["NOC"] = medals["NOC"].astype(str).str.strip().str.upper()

        # Prefer a stable country label per NOC (most frequent Team name)
        team_label = (
            medals.groupby(["games_id", "NOC"])["Team"]
            .agg(lambda s: s.astype(str).value_counts().index[0])
            .rename("country_name")
            .reset_index()
        )

        # Athlete-event medal counts by NOC (team events over-count vs official IOC tables)
        grp = (
            medals.groupby(["games_id", "NOC", "Medal"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        for col in ("Gold", "Silver", "Bronze"):
            if col not in grp.columns:
                grp[col] = 0
        grp = grp.merge(team_label, on=["games_id", "NOC"], how="left")

        count = 0
        for row in grp.itertuples(index=False):
            gold = int(getattr(row, "Gold", 0) or 0)
            silver = int(getattr(row, "Silver", 0) or 0)
            bronze = int(getattr(row, "Bronze", 0) or 0)
            noc = str(row.NOC)
            existing = self.session.scalar(
                select(MedalTable).where(
                    MedalTable.games_id == row.games_id,
                    MedalTable.noc_code == noc,
                    MedalTable.table_scope == "athlete_event_aggregate",
                )
            )
            if existing:
                existing.gold = gold
                existing.silver = silver
                existing.bronze = bronze
                existing.total = gold + silver + bronze
                existing.country_name = str(row.country_name)
                existing.verification_status = "collected"
            else:
                self.session.add(
                    MedalTable(
                        games_id=row.games_id,
                        noc_code=noc,
                        country_name=str(row.country_name),
                        gold=gold,
                        silver=silver,
                        bronze=bronze,
                        total=gold + silver + bronze,
                        table_scope="athlete_event_aggregate",
                        source_url=SOURCE_URL,
                        verification_status="collected",
                    )
                )
            count += 1
        return count

    def _enrich_games_counts(self, df: pd.DataFrame) -> None:
        for games_id, part in df.groupby("games_id"):
            game = self.session.get(Game, games_id)
            if not game:
                continue
            game.total_athletes = int(part["ID"].nunique())
            game.total_sports = int(part["Sport"].nunique())
            game.total_events = int(part["Event"].nunique())
            game.total_nocs = int(part["NOC"].nunique())
            males = part[part["Sex"] == "M"]["ID"].nunique()
            females = part[part["Sex"] == "F"]["ID"].nunique()
            game.male_athletes = int(males)
            game.female_athletes = int(females)
            game.source = SOURCE_NAME
            game.verification_status = "collected"
