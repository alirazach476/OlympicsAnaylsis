"""Shared enumeration values stored as strings in PostgreSQL."""

from __future__ import annotations

from enum import Enum


class Season(str, Enum):
    SUMMER = "summer"
    WINTER = "winter"


class VerificationStatus(str, Enum):
    COLLECTED = "collected"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"


class CrawlStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CRAWLED = "crawled"
    FAILED = "failed"
    SKIPPED = "skipped"
    EXCLUDED = "excluded"
    PAUSED = "paused"


class LinkType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    REDIRECT = "redirect"
    CATEGORY = "category"
    FILE = "file"
