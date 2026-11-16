"""SQLite-backed crawler persistence tests (no live Wikipedia calls)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.database.base import Base
import backend.models  # noqa: F401
from backend.models.core import Game
from backend.models.enums import CrawlStatus
from backend.models.wikipedia import CrawlQueue, WikipediaLink
from backend.scrapers.wikipedia.crawler import WikipediaOlympicsCrawler


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_queue_idempotent():
    session = _session()
    crawler = WikipediaOlympicsCrawler(session)
    n1 = crawler.seed_queue(["1960_summer"])
    n2 = crawler.seed_queue(["1960_summer"])
    assert n1 == 1
    assert n2 == 0
    game = session.get(Game, "1960_summer")
    assert game is not None
    assert game.season == "summer"
    q = session.scalar(select(CrawlQueue))
    assert q.status == CrawlStatus.PENDING.value
    assert q.depth == 0


def test_enqueue_and_link_graph():
    session = _session()
    crawler = WikipediaOlympicsCrawler(session)
    crawler.seed_queue(["1960_summer"])
    crawler._enqueue_child(
        games_id="1960_summer",
        title="Athletics at the 1960 Summer Olympics",
        url="https://en.wikipedia.org/wiki/Athletics_at_the_1960_Summer_Olympics",
        normalized_url="https://en.wikipedia.org/wiki/Athletics_at_the_1960_Summer_Olympics",
        parent_url="https://en.wikipedia.org/wiki/1960_Summer_Olympics",
        depth=1,
        page_category="sport_at_games",
        relevance_score=0.8,
    )
    crawler._upsert_link(
        games_id="1960_summer",
        source_title="1960 Summer Olympics",
        dest_title="Athletics at the 1960 Summer Olympics",
        source_url="https://en.wikipedia.org/wiki/1960_Summer_Olympics",
        dest_url="https://en.wikipedia.org/wiki/Athletics_at_the_1960_Summer_Olympics",
        source_norm="https://en.wikipedia.org/wiki/1960_Summer_Olympics",
        dest_norm="https://en.wikipedia.org/wiki/Athletics_at_the_1960_Summer_Olympics",
        link_text="Athletics",
        depth=1,
        parent="https://en.wikipedia.org/wiki/1960_Summer_Olympics",
        score=0.8,
        included=True,
        exclusion_reason=None,
        visited=False,
    )
    session.commit()
    pending = list(
        session.scalars(
            select(CrawlQueue).where(CrawlQueue.status == CrawlStatus.PENDING.value)
        )
    )
    assert len(pending) == 2
    link = session.scalar(select(WikipediaLink))
    assert link.included is True
    assert link.relevance_score == Decimal("0.8")
