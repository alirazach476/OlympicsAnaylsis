"""Resumable BFS Wikipedia crawler for Olympic edition page networks."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.collectors.editions import OlympicEdition, all_editions, get_edition
from backend.config import get_settings
from backend.models.core import Game
from backend.models.enums import CrawlStatus
from backend.models.wikipedia import CrawlHistory, CrawlQueue, WikipediaLink, WikipediaPage
from backend.scrapers.wikipedia.extractors import dumps, parse_html_bundle
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient, MediaWikiError
from backend.scrapers.wikipedia.relevance import score_relevance
from backend.scrapers.wikipedia.urls import (
    is_article_title_allowed,
    normalize_wikipedia_url,
    title_to_url,
)

logger = logging.getLogger(__name__)


@dataclass
class CrawlControls:
    max_depth: int = 3
    max_pages_per_edition: int = 500
    min_relevance_score: float = 0.45
    max_retries: int = 5
    games_ids: Optional[Sequence[str]] = None


@dataclass
class CrawlStats:
    enqueued: int = 0
    crawled: int = 0
    failed: int = 0
    skipped: int = 0
    excluded: int = 0
    links_discovered: int = 0


class WikipediaOlympicsCrawler:
    def __init__(self, session: Session, client: Optional[MediaWikiClient] = None):
        self.session = session
        self.client = client or MediaWikiClient()
        self.settings = get_settings()
        self.raw_pages_dir = Path(self.settings.raw_wikipedia_dir) / "pages"
        self.raw_pages_dir.mkdir(parents=True, exist_ok=True)
        # Dedupe enqueue/links within a single page crawl before DB flush
        self._enqueue_seen: set[tuple[str, str]] = set()
        self._link_seen: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------ seeds
    def ensure_games_rows(self, editions: Optional[Iterable[OlympicEdition]] = None) -> int:
        count = 0
        for edition in editions or all_editions():
            existing = self.session.get(Game, edition.games_id)
            if existing:
                continue
            self.session.add(
                Game(
                    games_id=edition.games_id,
                    year=edition.year,
                    season=edition.season,
                    official_edition_name=edition.official_edition_name,
                    edition_number=edition.edition_number,
                    host_city=edition.host_city,
                    host_country=edition.host_country,
                    opening_date=edition.opening_date,
                    closing_date=edition.closing_date,
                    actual_event_start_date=edition.actual_event_start_date,
                    actual_event_end_date=edition.actual_event_end_date,
                    wikipedia_url=edition.wikipedia_url,
                    olympedia_url=edition.olympedia_url,
                    official_website=edition.official_website,
                    source=edition.source,
                    verification_status=edition.verification_status,
                )
            )
            count += 1
        self.session.commit()
        return count

    def seed_queue(
        self,
        games_ids: Optional[Sequence[str]] = None,
        *,
        reset_failed: bool = False,
    ) -> int:
        editions = (
            [get_edition(g) for g in games_ids]
            if games_ids
            else all_editions()
        )
        self.ensure_games_rows(editions)
        added = 0
        for edition in editions:
            url = edition.wikipedia_url
            norm = normalize_wikipedia_url(url)
            assert norm
            existing = self.session.scalar(
                select(CrawlQueue).where(
                    CrawlQueue.games_id == edition.games_id,
                    CrawlQueue.normalized_url == norm,
                )
            )
            if existing:
                if reset_failed and existing.status == CrawlStatus.FAILED.value:
                    existing.status = CrawlStatus.PENDING.value
                    existing.attempts = 0
                    existing.last_error = None
                continue
            self.session.add(
                CrawlQueue(
                    games_id=edition.games_id,
                    title=edition.wikipedia_title,
                    url=url,
                    normalized_url=norm,
                    parent_url=None,
                    depth=0,
                    page_category="edition",
                    relevance_score=Decimal("1.0000"),
                    priority=0,
                    status=CrawlStatus.PENDING.value,
                )
            )
            added += 1
        self.session.commit()
        return added

    # ---------------------------------------------------------------- control
    def pause(self) -> None:
        path = Path(self.settings.crawl_pause_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("paused", encoding="utf-8")

    def resume(self) -> None:
        path = Path(self.settings.crawl_pause_file)
        if path.exists():
            path.unlink()

    def is_paused(self) -> bool:
        return Path(self.settings.crawl_pause_file).exists()

    def reclaim_stale_in_progress(self) -> int:
        """Reset interrupted in_progress queue rows back to pending (resume-safe)."""
        result = self.session.execute(
            update(CrawlQueue)
            .where(CrawlQueue.status == CrawlStatus.IN_PROGRESS.value)
            .values(status=CrawlStatus.PENDING.value)
        )
        self.session.commit()
        return int(result.rowcount or 0)

    def requeue_skipped_and_failed(
        self,
        games_ids: Optional[Sequence[str]] = None,
        *,
        include_failed: bool = True,
    ) -> int:
        """Re-open skipped/failed queue items so deeper crawls can follow sublinks."""
        statuses = [CrawlStatus.SKIPPED.value]
        if include_failed:
            statuses.append(CrawlStatus.FAILED.value)
        stmt = (
            update(CrawlQueue)
            .where(CrawlQueue.status.in_(statuses))
            .values(status=CrawlStatus.PENDING.value, last_error=None)
        )
        if games_ids:
            stmt = stmt.where(CrawlQueue.games_id.in_(list(games_ids)))
        result = self.session.execute(stmt)
        self.session.commit()
        return int(result.rowcount or 0)

    def enqueue_discovered_olympic_links(
        self,
        games_ids: Optional[Sequence[str]] = None,
        *,
        min_score: float = 0.45,
        max_depth: int = 3,
    ) -> int:
        """Promote already-discovered included Wikipedia links into the crawl queue."""
        from backend.models.wikipedia import WikipediaLink

        stmt = select(WikipediaLink).where(
            WikipediaLink.included.is_(True),
            WikipediaLink.relevance_score >= min_score,
            WikipediaLink.crawl_depth <= max_depth,
        )
        if games_ids:
            stmt = stmt.where(WikipediaLink.games_id.in_(list(games_ids)))
        added = 0
        for link in self.session.scalars(stmt).all():
            before = self.session.scalar(
                select(func.count())
                .select_from(CrawlQueue)
                .where(
                    CrawlQueue.games_id == link.games_id,
                    CrawlQueue.normalized_url == link.destination_normalized_url,
                )
            )
            self._enqueue_child(
                games_id=link.games_id,
                title=link.destination_page_title or link.destination_normalized_url,
                url=link.destination_url,
                normalized_url=link.destination_normalized_url,
                parent_url=link.source_url,
                depth=link.crawl_depth,
                page_category="discovered_link",
                relevance_score=float(link.relevance_score or 0),
            )
            after = self.session.scalar(
                select(func.count())
                .select_from(CrawlQueue)
                .where(
                    CrawlQueue.games_id == link.games_id,
                    CrawlQueue.normalized_url == link.destination_normalized_url,
                )
            )
            if (after or 0) > (before or 0):
                added += 1
            # Also reopen skipped queue rows for these URLs
        self.session.execute(
            update(CrawlQueue)
            .where(
                CrawlQueue.status == CrawlStatus.SKIPPED.value,
                *( [CrawlQueue.games_id.in_(list(games_ids))] if games_ids else [] ),
            )
            .values(status=CrawlStatus.PENDING.value, last_error=None)
        )
        self.session.commit()
        return added

    # ---------------------------------------------------------------- run
    def run(self, controls: Optional[CrawlControls] = None) -> CrawlStats:
        controls = controls or CrawlControls(
            max_depth=self.settings.crawl_max_depth,
            max_pages_per_edition=self.settings.crawl_max_pages_per_edition,
            min_relevance_score=self.settings.crawl_min_relevance_score,
            max_retries=self.settings.wiki_max_retries,
        )
        stats = CrawlStats()
        reclaimed = self.reclaim_stale_in_progress()
        if reclaimed:
            logger.info("Reclaimed %s interrupted in_progress queue item(s)", reclaimed)
        self.seed_queue(controls.games_ids)

        while True:
            if self.is_paused():
                logger.info("Crawl paused via pause file")
                break

            item = self._next_queue_item(controls.games_ids)
            if item is None:
                logger.info("Crawl queue empty")
                break

            edition = get_edition(item.games_id)
            crawled_count = self._crawled_count(item.games_id)
            if crawled_count >= controls.max_pages_per_edition:
                result = self.session.execute(
                    update(CrawlQueue)
                    .where(
                        CrawlQueue.games_id == item.games_id,
                        CrawlQueue.status == CrawlStatus.PENDING.value,
                    )
                    .values(
                        status=CrawlStatus.SKIPPED.value,
                        last_error="max_pages_per_edition_reached",
                    )
                )
                # Also skip the current item if somehow still pending/in_progress handling
                item.status = CrawlStatus.SKIPPED.value
                item.last_error = "max_pages_per_edition_reached"
                skipped_n = int(result.rowcount or 0) + 1
                self._history(
                    item,
                    "skip",
                    CrawlStatus.SKIPPED.value,
                    f"edition page cap bulk_skip={skipped_n}",
                )
                self.session.commit()
                stats.skipped += skipped_n
                logger.info(
                    "Edition %s hit max_pages=%s — skipped %s queued pages",
                    item.games_id,
                    controls.max_pages_per_edition,
                    skipped_n,
                )
                continue

            if item.depth > controls.max_depth:
                item.status = CrawlStatus.SKIPPED.value
                item.last_error = "max_depth_exceeded"
                self.session.commit()
                stats.skipped += 1
                continue

            item.status = CrawlStatus.IN_PROGRESS.value
            item.attempts += 1
            item.last_attempt_at = datetime.now(timezone.utc)
            self.session.commit()

            started = time.perf_counter()
            queue_id = item.queue_id
            item_url = item.normalized_url
            try:
                self._enqueue_seen.clear()
                self._link_seen.clear()
                discovered = self._crawl_one(item, edition, controls)
                stats.crawled += 1
                stats.links_discovered += discovered
                duration = int((time.perf_counter() - started) * 1000)
                self._history(
                    item,
                    "crawl",
                    CrawlStatus.CRAWLED.value,
                    f"ok links={discovered}",
                    duration_ms=duration,
                )
                self.session.commit()
            except Exception as exc:  # noqa: BLE001 - must continue crawl
                logger.exception("Failed crawling %s", item_url)
                self.session.rollback()
                item = self.session.get(CrawlQueue, queue_id)
                if item is None:
                    stats.failed += 1
                    continue
                item.last_error = str(exc)[:2000]
                item.attempts = (item.attempts or 0) + 0  # already incremented
                if item.attempts >= controls.max_retries:
                    item.status = CrawlStatus.FAILED.value
                    stats.failed += 1
                else:
                    item.status = CrawlStatus.PENDING.value
                self._history(item, "crawl", item.status, str(exc)[:500])
                self.session.commit()

        return stats

    def _next_queue_item(self, games_ids: Optional[Sequence[str]]) -> Optional[CrawlQueue]:
        stmt = (
            select(CrawlQueue)
            .where(CrawlQueue.status == CrawlStatus.PENDING.value)
            .order_by(CrawlQueue.priority.asc(), CrawlQueue.depth.asc(), CrawlQueue.queue_id.asc())
            .limit(1)
        )
        if games_ids:
            stmt = stmt.where(CrawlQueue.games_id.in_(list(games_ids)))
        return self.session.scalar(stmt)

    def _crawled_count(self, games_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(WikipediaPage)
                .where(
                    WikipediaPage.games_id == games_id,
                    WikipediaPage.crawl_status == CrawlStatus.CRAWLED.value,
                )
            )
            or 0
        )

    def _crawl_one(
        self,
        item: CrawlQueue,
        edition: OlympicEdition,
        controls: CrawlControls,
    ) -> int:
        title = item.title or item.normalized_url.rsplit("/", 1)[-1].replace("_", " ")
        logger.info(
            "Crawling [%s] depth=%s title=%s", item.games_id, item.depth, title
        )
        page = self.client.get_page_bundle(title)
        if page.get("missing"):
            item.status = CrawlStatus.FAILED.value
            item.last_error = "page_missing"
            raise MediaWikiError(f"Missing page: {title}")

        # Prefer canonical title after redirects
        canonical_title = page.get("title") or title
        canonical_url = page.get("fullurl") or title_to_url(canonical_title)
        norm = normalize_wikipedia_url(canonical_url) or item.normalized_url

        html = self.client.get_html(canonical_title)
        parsed = parse_html_bundle(html)

        categories = [c.get("title", "") for c in (page.get("categories") or [])]
        image_titles = [im.get("title") for im in (page.get("images") or []) if im.get("title")]
        # Keep metadata fetch small during crawl; asset pipeline expands later.
        image_meta = self.client.get_image_info(image_titles[:12]) if image_titles else []

        link_titles = self.client.get_links(canonical_title, max_links=1500)
        # Merge HTML-discovered links (captures link text)
        html_links = {l["title"]: l for l in parsed.get("html_links", [])}

        revisions = page.get("revisions") or []
        revision_id = None
        if revisions:
            revision_id = revisions[0].get("revid") or revisions[0].get("id")

        raw_payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "games_id": edition.games_id,
            "api_page": page,
            "parsed": {
                "infobox": parsed.get("infobox"),
                "headings": parsed.get("headings"),
                "tables": parsed.get("tables"),
                "references": parsed.get("references"),
                "html_images": parsed.get("html_images"),
            },
            "image_meta": image_meta,
            "link_titles": link_titles,
            "license": "CC BY-SA 4.0",
            "attribution": f"Wikipedia contributors — {canonical_url}",
        }
        raw_path = self._write_raw(edition.games_id, norm, raw_payload)

        rel = score_relevance(
            title=canonical_title,
            games_year=edition.year,
            season=edition.season,
            categories=categories,
            parent_title=None,
            depth=item.depth,
        )

        wp = self.session.scalar(
            select(WikipediaPage).where(WikipediaPage.normalized_url == norm)
        )
        if wp is None:
            wp = WikipediaPage(normalized_url=norm, url=canonical_url, title=canonical_title)
            self.session.add(wp)

        wp.games_id = edition.games_id
        wp.title = canonical_title
        wp.url = canonical_url
        wp.page_id = page.get("pageid")
        wp.revision_id = revision_id
        wp.summary = (page.get("extract") or "")[:4000] or None
        wp.content_extract = page.get("extract")
        wp.infobox_json = dumps(parsed.get("infobox") or {})
        wp.headings_json = dumps(parsed.get("headings") or [])
        wp.categories_json = dumps(categories)
        wp.references_json = dumps(parsed.get("references") or [])
        wp.images_json = dumps(image_meta)
        wp.tables_json = dumps(parsed.get("tables") or [])
        wp.raw_path = str(raw_path)
        wp.page_category = item.page_category or rel.page_category
        wp.relevance_score = Decimal(str(rel.score))
        wp.crawl_depth = item.depth
        wp.parent_url = item.parent_url
        wp.crawl_status = CrawlStatus.CRAWLED.value
        wp.last_crawl_time = datetime.now(timezone.utc)
        wp.error_message = None
        wp.verification_status = "collected"

        item.status = CrawlStatus.CRAWLED.value
        item.title = canonical_title
        # A redirect can resolve to a URL that already has its own queue row for this
        # edition (unique games_id+normalized_url). Keep this row's own URL in that case.
        clash = self.session.scalar(
            select(CrawlQueue.queue_id).where(
                CrawlQueue.games_id == item.games_id,
                CrawlQueue.normalized_url == norm,
                CrawlQueue.queue_id != item.queue_id,
            )
        )
        if clash is None:
            item.normalized_url = norm
            item.url = canonical_url

        discovered = 0
        for link_title in link_titles:
            if not is_article_title_allowed(link_title):
                continue
            dest_url = title_to_url(link_title)
            dest_norm = normalize_wikipedia_url(dest_url)
            if not dest_norm:
                continue
            link_text = (html_links.get(link_title) or {}).get("link_text")
            child_rel = score_relevance(
                title=link_title,
                games_year=edition.year,
                season=edition.season,
                categories=[],
                parent_title=canonical_title,
                link_text=link_text,
                depth=item.depth + 1,
            )
            included = (
                not child_rel.excluded
                and child_rel.score >= controls.min_relevance_score
                and (item.depth + 1) <= controls.max_depth
            )
            exclusion = None if included else (
                child_rel.exclusion_reason
                or f"score<{controls.min_relevance_score}"
            )

            self._upsert_link(
                games_id=edition.games_id,
                source_title=canonical_title,
                dest_title=link_title,
                source_url=canonical_url,
                dest_url=dest_url,
                source_norm=norm,
                dest_norm=dest_norm,
                link_text=link_text,
                depth=item.depth + 1,
                parent=canonical_url,
                score=child_rel.score,
                included=included,
                exclusion_reason=exclusion,
                visited=False,
            )
            discovered += 1

            if included:
                self._enqueue_child(
                    games_id=edition.games_id,
                    title=link_title,
                    url=dest_url,
                    normalized_url=dest_norm,
                    parent_url=canonical_url,
                    depth=item.depth + 1,
                    page_category=child_rel.page_category,
                    relevance_score=child_rel.score,
                )
            else:
                # Persist excluded destination discovery for audit
                self._ensure_discovered_page(
                    games_id=edition.games_id,
                    title=link_title,
                    url=dest_url,
                    normalized_url=dest_norm,
                    parent_url=canonical_url,
                    depth=item.depth + 1,
                    page_category=child_rel.page_category,
                    score=child_rel.score,
                    status=CrawlStatus.EXCLUDED.value,
                    error=exclusion,
                )

        # Mark outbound links from this page as visited source
        self.session.execute(
            update(WikipediaLink)
            .where(
                WikipediaLink.source_normalized_url == norm,
                WikipediaLink.games_id == edition.games_id,
            )
            .values(visited=True)
        )
        return discovered

    def _enqueue_child(self, **kwargs) -> None:
        key = (kwargs["games_id"], kwargs["normalized_url"])
        if key in self._enqueue_seen:
            return
        self._enqueue_seen.add(key)

        existing = self.session.scalar(
            select(CrawlQueue).where(
                CrawlQueue.games_id == kwargs["games_id"],
                CrawlQueue.normalized_url == kwargs["normalized_url"],
            )
        )
        if existing:
            # Prefer shallower discovery path; reopen skipped for deeper runs
            if existing.status == CrawlStatus.SKIPPED.value:
                existing.status = CrawlStatus.PENDING.value
                existing.last_error = None
            if kwargs["depth"] < existing.depth and existing.status in {
                CrawlStatus.PENDING.value,
                CrawlStatus.SKIPPED.value,
            }:
                existing.depth = kwargs["depth"]
                existing.parent_url = kwargs["parent_url"]
                existing.priority = min(
                    existing.priority, int(100 - kwargs["relevance_score"] * 100)
                )
            return
        # Also skip if already crawled
        crawled = self.session.scalar(
            select(WikipediaPage.wikipedia_page_id).where(
                WikipediaPage.normalized_url == kwargs["normalized_url"],
                WikipediaPage.crawl_status == CrawlStatus.CRAWLED.value,
            )
        )
        if crawled:
            return
        self.session.add(
            CrawlQueue(
                games_id=kwargs["games_id"],
                title=kwargs["title"],
                url=kwargs["url"],
                normalized_url=kwargs["normalized_url"],
                parent_url=kwargs["parent_url"],
                depth=kwargs["depth"],
                page_category=kwargs["page_category"],
                relevance_score=Decimal(str(kwargs["relevance_score"])),
                priority=int(100 - kwargs["relevance_score"] * 100),
                status=CrawlStatus.PENDING.value,
            )
        )

    def _ensure_discovered_page(self, **kwargs) -> None:
        wp = self.session.scalar(
            select(WikipediaPage).where(
                WikipediaPage.normalized_url == kwargs["normalized_url"]
            )
        )
        if wp:
            return
        self.session.add(
            WikipediaPage(
                games_id=kwargs["games_id"],
                title=kwargs["title"],
                url=kwargs["url"],
                normalized_url=kwargs["normalized_url"],
                parent_url=kwargs["parent_url"],
                crawl_depth=kwargs["depth"],
                page_category=kwargs["page_category"],
                relevance_score=Decimal(str(kwargs["score"])),
                crawl_status=kwargs["status"],
                error_message=kwargs.get("error"),
                verification_status="collected",
            )
        )

    def _upsert_link(self, **kwargs) -> None:
        link_key = (
            kwargs["games_id"],
            kwargs["source_norm"],
            kwargs["dest_norm"],
        )
        if link_key in self._link_seen:
            return
        self._link_seen.add(link_key)

        existing = self.session.scalar(
            select(WikipediaLink).where(
                WikipediaLink.games_id == kwargs["games_id"],
                WikipediaLink.source_normalized_url == kwargs["source_norm"],
                WikipediaLink.destination_normalized_url == kwargs["dest_norm"],
            )
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.link_text = kwargs.get("link_text") or existing.link_text
            existing.relevance_score = Decimal(str(kwargs["score"]))
            existing.included = kwargs["included"]
            existing.exclusion_reason = kwargs.get("exclusion_reason")
            existing.crawl_depth = kwargs["depth"]
            return
        self.session.add(
            WikipediaLink(
                games_id=kwargs["games_id"],
                source_page_title=kwargs["source_title"],
                destination_page_title=kwargs["dest_title"],
                source_url=kwargs["source_url"],
                destination_url=kwargs["dest_url"],
                source_normalized_url=kwargs["source_norm"],
                destination_normalized_url=kwargs["dest_norm"],
                link_text=kwargs.get("link_text"),
                link_type="internal",
                crawl_depth=kwargs["depth"],
                parent_page=kwargs.get("parent"),
                discovered_at=now,
                visited=kwargs.get("visited", False),
                relevance_score=Decimal(str(kwargs["score"])),
                exclusion_reason=kwargs.get("exclusion_reason"),
                included=kwargs["included"],
            )
        )

    def _write_raw(self, games_id: str, normalized_url: str, payload: dict) -> Path:
        edition_dir = self.raw_pages_dir / games_id
        edition_dir.mkdir(parents=True, exist_ok=True)
        slug = normalized_url.rsplit("/", 1)[-1][:180]
        path = edition_dir / f"{slug}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _history(
        self,
        item: CrawlQueue,
        action: str,
        status: str,
        message: str,
        duration_ms: Optional[int] = None,
    ) -> None:
        self.session.add(
            CrawlHistory(
                games_id=item.games_id,
                url=item.url,
                normalized_url=item.normalized_url,
                action=action,
                status=status,
                depth=item.depth,
                message=message,
                duration_ms=duration_ms,
                occurred_at=datetime.now(timezone.utc),
            )
        )

    # ------------------------------------------------------------- summaries
    def summarize(self, games_id: Optional[str] = None) -> dict:
        def _count(model, *filters):
            stmt = select(func.count()).select_from(model)
            for f in filters:
                stmt = stmt.where(f)
            return int(self.session.scalar(stmt) or 0)

        filters_q = []
        filters_p = []
        if games_id:
            filters_q.append(CrawlQueue.games_id == games_id)
            filters_p.append(WikipediaPage.games_id == games_id)

        return {
            "games_id": games_id,
            "queue_pending": _count(
                CrawlQueue, CrawlQueue.status == CrawlStatus.PENDING.value, *filters_q
            ),
            "queue_in_progress": _count(
                CrawlQueue, CrawlQueue.status == CrawlStatus.IN_PROGRESS.value, *filters_q
            ),
            "queue_failed": _count(
                CrawlQueue, CrawlQueue.status == CrawlStatus.FAILED.value, *filters_q
            ),
            "pages_crawled": _count(
                WikipediaPage, WikipediaPage.crawl_status == CrawlStatus.CRAWLED.value, *filters_p
            ),
            "pages_excluded": _count(
                WikipediaPage, WikipediaPage.crawl_status == CrawlStatus.EXCLUDED.value, *filters_p
            ),
            "pages_failed": _count(
                WikipediaPage, WikipediaPage.crawl_status == CrawlStatus.FAILED.value, *filters_p
            ),
            "links_total": _count(
                WikipediaLink,
                *( [WikipediaLink.games_id == games_id] if games_id else [] ),
            ),
            "links_included": _count(
                WikipediaLink,
                WikipediaLink.included.is_(True),
                *( [WikipediaLink.games_id == games_id] if games_id else [] ),
            ),
            "paused": self.is_paused(),
        }
