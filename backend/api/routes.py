from __future__ import annotations

import threading
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    CrawlHistoryOut,
    CrawlStartRequest,
    CrawlSummary,
    GameOut,
    MessageOut,
    OverviewStats,
    WikipediaLinkOut,
    WikipediaPageOut,
)
from backend.collectors.editions import all_editions
from backend.database.session import SessionLocal, get_db
from backend.models.core import Athlete, Event, EventResult, Game, MedalTable
from backend.models.enums import CrawlStatus
from backend.models.wikipedia import CrawlHistory, CrawlQueue, WikipediaLink, WikipediaPage
from backend.scrapers.wikipedia.crawler import CrawlControls, WikipediaOlympicsCrawler

router = APIRouter()
_crawl_lock = threading.Lock()
_crawl_thread: Optional[threading.Thread] = None


def _run_crawl(payload: CrawlStartRequest) -> None:
    session = SessionLocal()
    try:
        crawler = WikipediaOlympicsCrawler(session)
        crawler.resume()
        crawler.run(
            CrawlControls(
                max_depth=payload.max_depth,
                max_pages_per_edition=payload.max_pages_per_edition,
                min_relevance_score=payload.min_relevance_score,
                games_ids=payload.games_ids,
            )
        )
    finally:
        session.close()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "olympics-historical-platform"}


@router.get("/overview", response_model=OverviewStats)
def overview(db: Session = Depends(get_db)) -> OverviewStats:
    def c(model, *filters):
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        return int(db.scalar(stmt) or 0)

    return OverviewStats(
        games_total=c(Game),
        summer_games=c(Game, Game.season == "summer"),
        winter_games=c(Game, Game.season == "winter"),
        wikipedia_pages_crawled=c(
            WikipediaPage, WikipediaPage.crawl_status == CrawlStatus.CRAWLED.value
        ),
        wikipedia_pages_discovered=c(WikipediaPage),
        crawl_pending=c(CrawlQueue, CrawlQueue.status == CrawlStatus.PENDING.value),
        crawl_failed=c(CrawlQueue, CrawlQueue.status == CrawlStatus.FAILED.value),
        links_discovered=c(WikipediaLink),
        athletes=c(Athlete),
        events=c(Event),
        results=c(EventResult),
        medal_table_rows=c(MedalTable),
    )


@router.get("/games", response_model=List[GameOut])
def list_games(
    season: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Game]:
    stmt = select(Game).order_by(Game.year, Game.season)
    if season:
        stmt = stmt.where(Game.season == season.lower())
    rows = list(db.scalars(stmt).all())
    if not rows:
        # Fall back to seed registry view if DB not seeded yet
        editions = all_editions()
        if season:
            editions = [e for e in editions if e.season == season.lower()]
        return [
            GameOut(
                games_id=e.games_id,
                year=e.year,
                season=e.season,
                official_edition_name=e.official_edition_name,
                host_city=e.host_city,
                host_country=e.host_country,
                wikipedia_url=e.wikipedia_url,
                verification_status=e.verification_status,
            )
            for e in editions
        ]
    return rows


@router.get("/games/{games_id}", response_model=GameOut)
def get_game(games_id: str, db: Session = Depends(get_db)) -> Game:
    game = db.get(Game, games_id)
    if not game:
        raise HTTPException(404, f"games_id not found: {games_id}")
    return game


@router.get("/crawler/summary", response_model=CrawlSummary)
def crawler_summary(
    games_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> CrawlSummary:
    crawler = WikipediaOlympicsCrawler(db)
    return CrawlSummary(**crawler.summarize(games_id))


@router.post("/crawler/seed", response_model=MessageOut)
def crawler_seed(
    games_ids: Optional[List[str]] = None,
    db: Session = Depends(get_db),
) -> MessageOut:
    crawler = WikipediaOlympicsCrawler(db)
    created_games = crawler.ensure_games_rows()
    queued = crawler.seed_queue(games_ids)
    return MessageOut(
        message="Seeded crawl queue",
        detail={"games_inserted": created_games, "queue_added": queued},
    )


@router.post("/crawler/start", response_model=MessageOut)
def crawler_start(payload: CrawlStartRequest) -> MessageOut:
    global _crawl_thread
    with _crawl_lock:
        if _crawl_thread and _crawl_thread.is_alive():
            raise HTTPException(409, "Crawl already running")
        _crawl_thread = threading.Thread(target=_run_crawl, args=(payload,), daemon=True)
        _crawl_thread.start()
    return MessageOut(message="Crawl started", detail=payload.model_dump())


@router.post("/crawler/pause", response_model=MessageOut)
def crawler_pause(db: Session = Depends(get_db)) -> MessageOut:
    WikipediaOlympicsCrawler(db).pause()
    return MessageOut(message="Crawl pause requested")


@router.post("/crawler/resume", response_model=MessageOut)
def crawler_resume(payload: CrawlStartRequest) -> MessageOut:
    WikipediaOlympicsCrawler(SessionLocal()).resume()
    return crawler_start(payload)


@router.get("/crawler/pages", response_model=List[WikipediaPageOut])
def crawler_pages(
    games_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[WikipediaPageOut]:
    stmt = select(WikipediaPage).order_by(WikipediaPage.wikipedia_page_id.desc()).limit(limit)
    if games_id:
        stmt = stmt.where(WikipediaPage.games_id == games_id)
    if status:
        stmt = stmt.where(WikipediaPage.crawl_status == status)
    pages = list(db.scalars(stmt).all())
    out = []
    for p in pages:
        out.append(
            WikipediaPageOut(
                wikipedia_page_id=p.wikipedia_page_id,
                games_id=p.games_id,
                title=p.title,
                url=p.url,
                crawl_depth=p.crawl_depth,
                page_category=p.page_category,
                relevance_score=float(p.relevance_score) if p.relevance_score is not None else None,
                crawl_status=p.crawl_status,
                parent_url=p.parent_url,
                last_crawl_time=p.last_crawl_time.isoformat() if p.last_crawl_time else None,
            )
        )
    return out


@router.get("/crawler/links", response_model=List[WikipediaLinkOut])
def crawler_links(
    games_id: Optional[str] = None,
    included: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[WikipediaLinkOut]:
    stmt = select(WikipediaLink).order_by(WikipediaLink.wikipedia_link_id.desc()).limit(limit)
    if games_id:
        stmt = stmt.where(WikipediaLink.games_id == games_id)
    if included is not None:
        stmt = stmt.where(WikipediaLink.included.is_(included))
    links = list(db.scalars(stmt).all())
    return [
        WikipediaLinkOut(
            wikipedia_link_id=l.wikipedia_link_id,
            games_id=l.games_id,
            source_page_title=l.source_page_title,
            destination_page_title=l.destination_page_title,
            crawl_depth=l.crawl_depth,
            relevance_score=float(l.relevance_score) if l.relevance_score is not None else None,
            included=l.included,
            exclusion_reason=l.exclusion_reason,
            visited=l.visited,
        )
        for l in links
    ]


@router.get("/crawler/history", response_model=List[CrawlHistoryOut])
def crawler_history(
    games_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[CrawlHistoryOut]:
    stmt = select(CrawlHistory).order_by(CrawlHistory.history_id.desc()).limit(limit)
    if games_id:
        stmt = stmt.where(CrawlHistory.games_id == games_id)
    rows = list(db.scalars(stmt).all())
    return [
        CrawlHistoryOut(
            history_id=r.history_id,
            games_id=r.games_id,
            url=r.url,
            action=r.action,
            status=r.status,
            depth=r.depth,
            message=r.message,
            occurred_at=r.occurred_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/crawler/queue")
def crawler_queue(
    games_id: Optional[str] = None,
    status: Optional[str] = "pending",
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list:
    stmt = select(CrawlQueue).order_by(CrawlQueue.priority, CrawlQueue.depth).limit(limit)
    if games_id:
        stmt = stmt.where(CrawlQueue.games_id == games_id)
    if status:
        stmt = stmt.where(CrawlQueue.status == status)
    rows = list(db.scalars(stmt).all())
    return [
        {
            "queue_id": r.queue_id,
            "games_id": r.games_id,
            "title": r.title,
            "url": r.url,
            "depth": r.depth,
            "relevance_score": float(r.relevance_score) if r.relevance_score is not None else None,
            "status": r.status,
            "parent_url": r.parent_url,
            "page_category": r.page_category,
        }
        for r in rows
    ]
