"""Olympic relevance scoring to keep the crawler inside the Olympic subgraph."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

OLYMPIC_KEYWORDS = (
    "olympic",
    "olympics",
    "olympiad",
    "olympian",
    "medal",
    "medalist",
    "medallist",
    "noc",
    "paralympic",  # related; scored lower unless edition-tied
)

SPORT_KEYWORDS = (
    "athletics",
    "swimming",
    "football",
    "soccer",
    "basketball",
    "volleyball",
    "handball",
    "hockey",
    "water polo",
    "rugby",
    "baseball",
    "softball",
    "tennis",
    "boxing",
    "wrestling",
    "judo",
    "taekwondo",
    "fencing",
    "cycling",
    "rowing",
    "canoe",
    "kayak",
    "sailing",
    "gymnastics",
    "weightlifting",
    "archery",
    "shooting",
    "diving",
    "triathlon",
    "modern pentathlon",
    "equestrian",
    "badminton",
    "table tennis",
    "golf",
    "skateboarding",
    "surfing",
    "sport climbing",
    "breaking",
    "ice hockey",
    "figure skating",
    "speed skating",
    "short track",
    "alpine skiing",
    "cross-country skiing",
    "ski jumping",
    "nordic combined",
    "biathlon",
    "bobsleigh",
    "luge",
    "skeleton",
    "curling",
    "snowboarding",
    "freestyle skiing",
)

CONTEXT_KEYWORDS = (
    "opening ceremony",
    "closing ceremony",
    "medal table",
    "participating nations",
    "national olympic committee",
    "olympic village",
    "venue",
    "mascot",
    "torch relay",
    "qualification",
    "results",
    "tournament",
)

EXCLUDE_TITLE_PATTERNS = (
    r"^List of songs",
    r"discography",
    r"filmography",
    r"\bTV series\b",
    r"\balbum\b",
    r"^Timeline of",
    r"conspiracy",
)

INCLUDE_CATEGORY_HINTS = (
    "olympic",
    "olympics",
    "olympiad",
    "medal",
    "sports at the",
)


@dataclass
class RelevanceResult:
    score: float
    reasons: List[str]
    page_category: str
    excluded: bool
    exclusion_reason: Optional[str] = None


def _contains_any(text: str, keywords: Sequence[str]) -> List[str]:
    text_l = text.lower()
    return [k for k in keywords if k in text_l]


def classify_page_category(title: str) -> str:
    t = title.lower()
    if re.search(r"\b\d{4}\s+(summer|winter)\s+olympics\b", t) and "at the" not in t:
        if "medal table" in t:
            return "medal_table"
        if "opening ceremony" in t:
            return "opening_ceremony"
        if "closing ceremony" in t:
            return "closing_ceremony"
        return "edition"
    if "medal table" in t:
        return "medal_table"
    if re.search(r" at the \d{4} (summer|winter) olympics", t):
        if " – " in title or " - " in title or "men" in t or "women" in t:
            return "event"
        return "sport_at_games"
    if "olympic" in t and "venue" in t:
        return "venue"
    if "national olympic committee" in t or t.endswith(" at the olympics"):
        return "noc_or_nation"
    if any(s in t for s in SPORT_KEYWORDS) and "olympic" in t:
        return "sport"
    return "related"


def score_relevance(
    *,
    title: str,
    games_year: int,
    season: str,
    categories: Optional[Iterable[str]] = None,
    parent_title: Optional[str] = None,
    link_text: Optional[str] = None,
    depth: int = 0,
) -> RelevanceResult:
    reasons: List[str] = []
    score = 0.0
    categories = list(categories or [])
    title_l = title.lower()
    season_l = season.lower()
    year_str = str(games_year)

    for pattern in EXCLUDE_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return RelevanceResult(
                score=0.0,
                reasons=["excluded_by_title_pattern"],
                page_category="excluded",
                excluded=True,
                exclusion_reason=f"title_pattern:{pattern}",
            )

    # Strong: exact edition binding — follow these links/sublinks aggressively
    edition_phrase = f"{year_str} {season_l} olympics"
    at_edition = f"at the {edition_phrase}"
    if title_l == edition_phrase or title_l.startswith(edition_phrase + " "):
        score += 0.7
        reasons.append("title_is_edition_or_edition_subpage")
    elif at_edition in title_l:
        # Sport/event pages for this edition (primary discovery frontier)
        score += 0.85
        reasons.append("title_at_this_edition")
    elif edition_phrase in title_l:
        score += 0.65
        reasons.append("title_contains_edition")
    elif year_str in title_l and "olympic" in title_l:
        score += 0.35
        reasons.append("title_year_and_olympic")
    elif "olympic" in title_l:
        score += 0.2
        reasons.append("title_olympic")

    if season_l in title_l and "olympic" in title_l:
        score += 0.1
        reasons.append("title_season")

    hits = _contains_any(title_l, SPORT_KEYWORDS)
    if hits and ("olympic" in title_l or year_str in title_l or at_edition in title_l):
        score += 0.2
        reasons.append(f"sport_keywords:{','.join(hits[:3])}")

    ctx = _contains_any(title_l, CONTEXT_KEYWORDS)
    if ctx:
        score += 0.2
        reasons.append(f"context:{','.join(ctx[:3])}")

    # Athlete / nation pages strongly tied via parent edition page
    if parent_title and at_edition in parent_title.lower() and score < 0.5:
        if "olympic" in title_l or year_str in title_l:
            score += 0.25
            reasons.append("child_of_edition_sport_page")

    cat_text = " | ".join(categories).lower()
    cat_hits = _contains_any(cat_text, INCLUDE_CATEGORY_HINTS)
    if cat_hits:
        score += 0.2
        reasons.append("olympic_categories")

    if parent_title and edition_phrase in parent_title.lower():
        score += 0.1
        reasons.append("parent_is_edition")

    if link_text:
        lt = link_text.lower()
        if edition_phrase in lt or "medal" in lt:
            score += 0.05
            reasons.append("link_text_boost")

    # Penalize Paralympic-only drift unless edition-tied
    if "paralympic" in title_l and edition_phrase not in title_l:
        score -= 0.25
        reasons.append("paralympic_penalty")

    # Depth decay — prefer near-seed pages
    score -= min(depth * 0.05, 0.25)
    if depth:
        reasons.append(f"depth_penalty:{depth}")

    score = max(0.0, min(1.0, score))
    page_category = classify_page_category(title)

    # Hard exclude: unrelated high-traffic pages without olympic signal
    if score < 0.2 and "olympic" not in title_l and not cat_hits:
        return RelevanceResult(
            score=score,
            reasons=reasons + ["below_hard_floor"],
            page_category=page_category,
            excluded=True,
            exclusion_reason="relevance_below_hard_floor",
        )

    return RelevanceResult(
        score=round(score, 4),
        reasons=reasons,
        page_category=page_category,
        excluded=False,
    )
