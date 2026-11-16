from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GameOut(BaseModel):
    games_id: str
    year: int
    season: str
    official_edition_name: str
    host_city: Optional[str] = None
    host_country: Optional[str] = None
    wikipedia_url: Optional[str] = None
    verification_status: str

    model_config = {"from_attributes": True}


class CrawlStartRequest(BaseModel):
    games_ids: Optional[List[str]] = None
    max_depth: int = Field(default=2, ge=0, le=8)
    max_pages_per_edition: int = Field(default=25, ge=1, le=5000)
    min_relevance_score: float = Field(default=0.45, ge=0.0, le=1.0)


class CrawlSummary(BaseModel):
    games_id: Optional[str] = None
    queue_pending: int
    queue_in_progress: int
    queue_failed: int
    pages_crawled: int
    pages_excluded: int
    pages_failed: int
    links_total: int
    links_included: int
    paused: bool


class OverviewStats(BaseModel):
    games_total: int
    summer_games: int
    winter_games: int
    wikipedia_pages_crawled: int
    wikipedia_pages_discovered: int
    crawl_pending: int
    crawl_failed: int
    links_discovered: int
    athletes: int
    events: int
    results: int
    medal_table_rows: int


class WikipediaPageOut(BaseModel):
    wikipedia_page_id: int
    games_id: Optional[str]
    title: str
    url: str
    crawl_depth: int
    page_category: Optional[str]
    relevance_score: Optional[float]
    crawl_status: str
    parent_url: Optional[str]
    last_crawl_time: Optional[str]

    model_config = {"from_attributes": True}


class WikipediaLinkOut(BaseModel):
    wikipedia_link_id: int
    games_id: Optional[str]
    source_page_title: Optional[str]
    destination_page_title: Optional[str]
    crawl_depth: int
    relevance_score: Optional[float]
    included: bool
    exclusion_reason: Optional[str]
    visited: bool

    model_config = {"from_attributes": True}


class CrawlHistoryOut(BaseModel):
    history_id: int
    games_id: Optional[str]
    url: str
    action: str
    status: str
    depth: Optional[int]
    message: Optional[str]
    occurred_at: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message: str
    detail: Optional[Dict[str, Any]] = None
