"""Wikipedia crawl graph, queue, and history models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
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


class WikipediaPage(Base, TimestampMixin):
    __tablename__ = "wikipedia_pages"
    __table_args__ = (
        UniqueConstraint("normalized_url", name="uq_wikipedia_pages_url"),
        Index("ix_wikipedia_pages_games_status", "games_id", "crawl_status"),
        Index("ix_wikipedia_pages_page_id", "page_id"),
    )

    wikipedia_page_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    page_id: Mapped[Optional[int]] = mapped_column(Integer)
    revision_id: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content_extract: Mapped[Optional[str]] = mapped_column(Text)
    infobox_json: Mapped[Optional[str]] = mapped_column(Text)
    headings_json: Mapped[Optional[str]] = mapped_column(Text)
    categories_json: Mapped[Optional[str]] = mapped_column(Text)
    references_json: Mapped[Optional[str]] = mapped_column(Text)
    images_json: Mapped[Optional[str]] = mapped_column(Text)
    tables_json: Mapped[Optional[str]] = mapped_column(Text)
    raw_path: Mapped[Optional[str]] = mapped_column(String(1024))
    page_category: Mapped[Optional[str]] = mapped_column(String(128))
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    crawl_depth: Mapped[int] = mapped_column(Integer, default=0)
    parent_url: Mapped[Optional[str]] = mapped_column(String(1024))
    crawl_status: Mapped[str] = mapped_column(String(32), default="pending")
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    license: Mapped[str] = mapped_column(String(64), default="CC BY-SA 4.0")
    attribution: Mapped[str] = mapped_column(
        String(512), default="Wikipedia contributors — https://en.wikipedia.org/"
    )
    verification_status: Mapped[str] = mapped_column(String(32), default="collected")

    game = relationship("Game", back_populates="wikipedia_pages")


class WikipediaLink(Base, TimestampMixin):
    __tablename__ = "wikipedia_links"
    __table_args__ = (
        UniqueConstraint(
            "source_normalized_url",
            "destination_normalized_url",
            "games_id",
            name="uq_wikipedia_link",
        ),
        Index("ix_wikipedia_links_games", "games_id"),
    )

    wikipedia_link_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    source_page_title: Mapped[Optional[str]] = mapped_column(String(512))
    destination_page_title: Mapped[Optional[str]] = mapped_column(String(512))
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_normalized_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    destination_normalized_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    link_text: Mapped[Optional[str]] = mapped_column(String(512))
    link_type: Mapped[str] = mapped_column(String(32), default="internal")
    crawl_depth: Mapped[int] = mapped_column(Integer, default=0)
    parent_page: Mapped[Optional[str]] = mapped_column(String(1024))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visited: Mapped[bool] = mapped_column(Boolean, default=False)
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(512))
    included: Mapped[bool] = mapped_column(Boolean, default=True)


class CrawlQueue(Base, TimestampMixin):
    __tablename__ = "crawl_queue"
    __table_args__ = (
        UniqueConstraint("normalized_url", "games_id", name="uq_crawl_queue_item"),
        Index("ix_crawl_queue_status_priority", "status", "priority", "depth"),
    )

    queue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[str] = mapped_column(ForeignKey("games.games_id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    parent_url: Mapped[Optional[str]] = mapped_column(String(1024))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    page_category: Mapped[Optional[str]] = mapped_column(String(128))
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CrawlHistory(Base, TimestampMixin):
    __tablename__ = "crawl_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_id: Mapped[Optional[str]] = mapped_column(ForeignKey("games.games_id"))
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    depth: Mapped[Optional[int]] = mapped_column(Integer)
    message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
