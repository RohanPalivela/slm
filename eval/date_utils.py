"""Shared best-effort date parsing for APUSH item audits.

The prompt emits free-text `answer_dating`, so these helpers intentionally avoid
overclaiming precision. They parse explicit years plus common decade phrases into
spans, allowing checks to distinguish "clearly before/after" from "ambiguous but
not provably wrong."
"""
from __future__ import annotations

import re

_YEAR = re.compile(r"\b(1[4-9]\d\d|20\d\d)s?\b")
_DECADE = re.compile(
    r"\b(?:(early|mid|late)[ -]+)?((?:1[4-9]|20)\d0)s\b",
    re.I,
)
_BEFORE_CUE = re.compile(r"\b(?:before|prior to|preced(?:e|ed|ing)|pre-dates?|predates?)\b", re.I)
_AFTER_CUE = re.compile(r"\b(?:after|following|later|subsequent(?:ly)?|postdates?)\b", re.I)


def source_year(source: dict | None) -> int | None:
    if not source:
        return None
    year = source.get("year")
    if isinstance(year, list):
        year = year[0] if year else None
    if isinstance(year, int):
        return year
    return None


def date_spans(text: str) -> list[tuple[int, int]]:
    """Return `(start_year, end_year)` spans from free-text date language.

    Examples:
      - "1896" -> (1896, 1896)
      - "late 1890s" -> (1897, 1899)
      - "early 1940s" -> (1940, 1943)
      - "mid-1830s" -> (1834, 1836)
      - "1890s" -> (1890, 1899)
    """
    text = text or ""
    spans: list[tuple[int, int]] = []
    decade_ranges: list[tuple[int, int, int, int]] = []

    for match in _DECADE.finditer(text):
        qual = (match.group(1) or "").lower()
        decade = int(match.group(2))
        if qual == "early":
            span = (decade, decade + 3)
        elif qual == "mid":
            span = (decade + 4, decade + 6)
        elif qual == "late":
            span = (decade + 7, decade + 9)
        else:
            span = (decade, decade + 9)
        spans.append(span)
        decade_ranges.append((match.start(), match.end(), span[0], span[1]))

    for match in _YEAR.finditer(text):
        year = int(match.group(1))
        # Avoid adding the bare decade anchor inside "late 1890s" a second time.
        if any(start <= match.start() < end for start, end, _, _ in decade_ranges):
            continue
        spans.append((year, year))

    return spans


def years_in(text: str) -> list[int]:
    """Compatibility helper: return representative years from parsed spans."""
    return [end for _, end in date_spans(text)]


def direction_against_source(archetype: str, answer_dating: str, src_year: int | None,
                             cause_archetypes: set[str],
                             effect_archetypes: set[str]) -> str:
    """'pass' | 'fail' | 'unknown' for cause/effect date direction.

    For spans, fail only when every parsed span is clearly on the wrong side of
    the source year. Ambiguous overlapping spans are not marked fail.
    """
    if src_year is None or (archetype not in cause_archetypes and archetype not in effect_archetypes):
        return "unknown"
    spans = [(start, end) for start, end in date_spans(answer_dating) if not (start == end == src_year)]
    if not spans:
        before = bool(_BEFORE_CUE.search(answer_dating or ""))
        after = bool(_AFTER_CUE.search(answer_dating or ""))
        if before != after:
            if archetype in cause_archetypes:
                return "pass" if before else "fail"
            return "pass" if after else "fail"
        return "unknown"
    if archetype in cause_archetypes:
        # A cause fails only if all evidence starts after the source.
        return "fail" if min(start for start, _ in spans) > src_year else "pass"
    # An effect fails only if all evidence ends before or at the source.
    return "fail" if max(end for _, end in spans) <= src_year else "pass"
