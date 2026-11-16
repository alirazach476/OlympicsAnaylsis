"""Core Olympic domain models: games, countries, sports, athletes, results."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, TimestampMixin


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(512))
    license: Mapped[Optional[str]] = mapped_column(String(256))
    authority_rank: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class SourcePage(Base, TimestampMixin):
    __tablename__ = "source_pages"
    __table_args__ = (UniqueConstraint("source_id", "url", name="uq_source_pages_url"),)

    source_page_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    raw_path: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Game(Base, TimestampMixin):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("year", "season", name="uq_games_year_season"),
        Index("ix_games_season_year", "season", "year"),
    )

    games_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g. 1960_summer
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[str] = mapped_column(String(16), nullable=False)
    official_edition_name: Mapped[str] = mapped_column(String(256), nullable=False)
    edition_number: Mapped[Optional[int]] = mapped_column(Integer)
    host_city: Mapped[Optional[str]] = mapped_column(String(128))
    host_country: Mapped[Optional[str]] = mapped_column(String(128))
    opening_date: Mapped[Optional[date]] = mapped_column(Date)
    closing_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_event_start_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_event_end_date: Mapped[Optional[date]] = mapped_column(Date)
    total_nocs: Mapped[Optional[int]] = mapped_column(Integer)
    total_athletes: Mapped[Optional[int]] = mapped_column(Integer)
    male_athletes: Mapped[Optional[int]] = mapped_column(Integer)
    female_athletes: Mapped[Optional[int]] = mapped_column(Integer)
    total_sports: Mapped[Optional[int]] = mapped_column(Integer)
    total_disciplines: Mapped[Optional[int]] = mapped_column(Integer)
    total_events: Mapped[Optional[int]] = mapped_column(Integer)
    official_logo: Mapped[Optional[str]] = mapped_column(String(1024))
    official_website: Mapped[Optional[str]] = mapped_column(String(512))
    wikipedia_url: Mapped[Optional[str]] = mapped_column(String(512))
    olympedia_url: Mapped[Optional[str]] = mapped_column(String(512))
    source: Mapped[Optional[str]] = mapped_column(String(128))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    wikipedia_pages = relationship("WikipediaPage", back_populates="game")


class Country(Base, TimestampMixin):
    __tablename__ = "countries"

    country_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    current_country_name: Mapped[Optional[str]] = mapped_column(String(256))
    continent: Mapped[Optional[str]] = mapped_column(String(64))
    flag_url: Mapped[Optional[str]] = mapped_column(String(1024))
    iso_alpha2: Mapped[Optional[str]] = mapped_column(String(2))
    iso_alpha3: Mapped[Optional[str]] = mapped_column(String(3))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class HistoricalNOC(Base, TimestampMixin):
    __tablename__ = "historical_nocs"
    __table_args__ = (UniqueConstraint("noc_code", "valid_from_year", name="uq_noc_code_from"),)

    historical_noc_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    noc_code: Mapped[str] = mapped_column(String(8), nullable=False)
    historical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    current_country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.country_id"))
    continent: Mapped[Optional[str]] = mapped_column(String(64))
    flag_url: Mapped[Optional[str]] = mapped_column(String(1024))
    first_olympic_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    last_olympic_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    olympic_appearances: Mapped[Optional[int]] = mapped_column(Integer)
    total_athletes: Mapped[Optional[int]] = mapped_column(Integer)
    total_medals: Mapped[Optional[int]] = mapped_column(Integer)
    is_unified_or_neutral: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    valid_from_year: Mapped[Optional[int]] = mapped_column(Integer)
    valid_to_year: Mapped[Optional[int]] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Sport(Base, TimestampMixin):
    __tablename__ = "sports"

    sport_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    season: Mapped[Optional[str]] = mapped_column(String(16))  # summer/winter/both
    first_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    last_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    number_of_events: Mapped[Optional[int]] = mapped_column(Integer)
    mens_events: Mapped[Optional[int]] = mapped_column(Integer)
    womens_events: Mapped[Optional[int]] = mapped_column(Integer)
    mixed_events: Mapped[Optional[int]] = mapped_column(Integer)
    sport_logo: Mapped[Optional[str]] = mapped_column(String(1024))
    sport_image: Mapped[Optional[str]] = mapped_column(String(1024))
    is_demonstration: Mapped[bool] = mapped_column(Boolean, default=False)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    disciplines = relationship("Discipline", back_populates="sport")


class Discipline(Base, TimestampMixin):
    __tablename__ = "disciplines"
    __table_args__ = (UniqueConstraint("sport_id", "discipline_name", name="uq_discipline"),)

    discipline_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.sport_id"), nullable=False)
    discipline_name: Mapped[str] = mapped_column(String(128), nullable=False)
    season: Mapped[Optional[str]] = mapped_column(String(16))
    first_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    last_appearance: Mapped[Optional[int]] = mapped_column(Integer)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    sport = relationship("Sport", back_populates="disciplines")


class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("games_id", "discipline_id", "event_name", "event_gender", name="uq_event"),
    )

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    discipline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("disciplines.discipline_id"))
    event_name: Mapped[str] = mapped_column(String(256), nullable=False)
    event_gender: Mapped[Optional[str]] = mapped_column(String(32))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Athlete(Base, TimestampMixin):
    __tablename__ = "athletes"
    __table_args__ = (Index("ix_athletes_full_name", "full_name"),)

    athlete_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String(256))
    gender: Mapped[Optional[str]] = mapped_column(String(32))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    date_of_death: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(128))
    height_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    biography: Mapped[Optional[str]] = mapped_column(Text)
    athlete_image: Mapped[Optional[str]] = mapped_column(String(1024))
    identity_key: Mapped[Optional[str]] = mapped_column(String(512), unique=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    participations = relationship("AthleteParticipation", back_populates="athlete")


class AthleteParticipation(Base, TimestampMixin):
    __tablename__ = "athlete_participations"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id", "games_id", "event_id", "noc_code",
            name="uq_athlete_participation",
        ),
    )

    participation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.athlete_id"), nullable=False)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    discipline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("disciplines.discipline_id"))
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.event_id"))
    noc_code: Mapped[Optional[str]] = mapped_column(String(8))
    country: Mapped[Optional[str]] = mapped_column(String(128))
    team: Mapped[Optional[str]] = mapped_column(String(256))
    age_at_competition: Mapped[Optional[int]] = mapped_column(Integer)
    participation_status: Mapped[Optional[str]] = mapped_column(String(64))
    medal: Mapped[Optional[str]] = mapped_column(String(16))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    athlete = relationship("Athlete", back_populates="participations")


class Team(Base, TimestampMixin):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("games_id", "sport_id", "noc_code", "team_name", name="uq_team"),
    )

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    discipline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("disciplines.discipline_id"))
    noc_code: Mapped[Optional[str]] = mapped_column(String(8))
    team_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "athlete_id", name="uq_team_member"),)

    team_member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), nullable=False)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.athlete_id"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(64))
    jersey_number: Mapped[Optional[str]] = mapped_column(String(16))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class EventResult(Base, TimestampMixin):
    __tablename__ = "event_results"
    __table_args__ = (
        Index("ix_event_results_games_event", "games_id", "event_id"),
    )

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    discipline_id: Mapped[Optional[int]] = mapped_column(ForeignKey("disciplines.discipline_id"))
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.event_id"))
    event_name: Mapped[Optional[str]] = mapped_column(String(256))
    event_gender: Mapped[Optional[str]] = mapped_column(String(32))
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.athlete_id"))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    noc_code: Mapped[Optional[str]] = mapped_column(String(8))
    round: Mapped[Optional[str]] = mapped_column(String(64))
    heat: Mapped[Optional[str]] = mapped_column(String(64))
    qualification_position: Mapped[Optional[int]] = mapped_column(Integer)
    final_position: Mapped[Optional[int]] = mapped_column(Integer)
    result_value: Mapped[Optional[str]] = mapped_column(String(128))
    result_unit: Mapped[Optional[str]] = mapped_column(String(64))
    medal: Mapped[Optional[str]] = mapped_column(String(16))
    olympic_record: Mapped[bool] = mapped_column(Boolean, default=False)
    world_record: Mapped[bool] = mapped_column(Boolean, default=False)
    result_status: Mapped[Optional[str]] = mapped_column(String(64))
    disqualification_reason: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Medal(Base, TimestampMixin):
    __tablename__ = "medals"

    medal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.event_id"))
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.athlete_id"))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    noc_code: Mapped[Optional[str]] = mapped_column(String(8))
    medal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    is_team_medal: Mapped[bool] = mapped_column(Boolean, default=False)
    reallocation_note: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class MedalTable(Base, TimestampMixin):
    __tablename__ = "medal_tables"
    __table_args__ = (
        UniqueConstraint("games_id", "noc_code", "table_scope", name="uq_medal_table"),
    )

    medal_table_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    noc_code: Mapped[str] = mapped_column(String(8), nullable=False)
    country_name: Mapped[Optional[str]] = mapped_column(String(256))
    gold: Mapped[int] = mapped_column(Integer, default=0)
    silver: Mapped[int] = mapped_column(Integer, default=0)
    bronze: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    official_rank: Mapped[Optional[int]] = mapped_column(Integer)
    table_scope: Mapped[str] = mapped_column(String(64), default="official_country")
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.event_id"))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    sport_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sports.sport_id"))
    tournament_name: Mapped[Optional[str]] = mapped_column(String(256))
    match_date: Mapped[Optional[date]] = mapped_column(Date)
    match_stage: Mapped[Optional[str]] = mapped_column(String(128))
    group_name: Mapped[Optional[str]] = mapped_column(String(64))
    home_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    away_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    home_score: Mapped[Optional[str]] = mapped_column(String(64))
    away_score: Mapped[Optional[str]] = mapped_column(String(64))
    period_scores: Mapped[Optional[str]] = mapped_column(Text)
    match_status: Mapped[Optional[str]] = mapped_column(String(64))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class MatchResult(Base, TimestampMixin):
    __tablename__ = "match_results"

    match_result_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.match_id"), nullable=False)
    winner_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    final_ranking_home: Mapped[Optional[int]] = mapped_column(Integer)
    final_ranking_away: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class MatchStatistic(Base, TimestampMixin):
    __tablename__ = "match_statistics"

    match_stat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.match_id"), nullable=False)
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.athlete_id"))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.team_id"))
    goals: Mapped[Optional[int]] = mapped_column(Integer)
    assists: Mapped[Optional[int]] = mapped_column(Integer)
    points: Mapped[Optional[int]] = mapped_column(Integer)
    cards: Mapped[Optional[str]] = mapped_column(String(64))
    penalties: Mapped[Optional[str]] = mapped_column(String(64))
    minutes_played: Mapped[Optional[int]] = mapped_column(Integer)
    extra_stats_json: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    venue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    venue_name: Mapped[str] = mapped_column(String(256), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(128))
    country: Mapped[Optional[str]] = mapped_column(String(128))
    sport: Mapped[Optional[str]] = mapped_column(String(128))
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    venue_image: Mapped[Optional[str]] = mapped_column(String(1024))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Record(Base, TimestampMixin):
    __tablename__ = "records"

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.event_id"))
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.athlete_id"))
    noc_code: Mapped[Optional[str]] = mapped_column(String(8))
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_value: Mapped[Optional[str]] = mapped_column(String(128))
    record_unit: Mapped[Optional[str]] = mapped_column(String(64))
    record_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Mascot(Base, TimestampMixin):
    __tablename__ = "mascots"

    mascot_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    local_path: Mapped[Optional[str]] = mapped_column(String(1024))
    remote_url: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    author: Mapped[Optional[str]] = mapped_column(String(256))
    license: Mapped[Optional[str]] = mapped_column(String(256))
    attribution: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_page: Mapped[Optional[str]] = mapped_column(String(1024))
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")


class DataQualityReport(Base, TimestampMixin):
    __tablename__ = "data_quality_reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    report_path: Mapped[Optional[str]] = mapped_column(String(1024))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
