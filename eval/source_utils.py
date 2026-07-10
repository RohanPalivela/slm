"""Small shared helpers for stratifying APUSH sources in reports."""
from __future__ import annotations

import re


def source_genre(source: dict | None = None, source_id: str = "") -> str:
    """Return a stable, coarse genre used for train/eval shift diagnostics."""
    source = source or {}
    sid = str(source.get("id") or source_id or "").lower()
    text = " ".join(
        str(source.get(k) or "") for k in ("attribution", "author", "provenance")
    ).lower()
    blob = f"{sid} {text}"
    if re.search(r"\b(v\.?|court|justice|opinion|marbury|mcculloch|worcester|dred_scott|plessy|schenck)\b", blob):
        return "court_opinion"
    if re.search(r"\b(treaty|compact)\b", blob):
        return "treaty_or_compact"
    if re.search(r"\b(executive[_ ]order|proclamation)\b", blob):
        return "executive_action"
    if re.search(r"\b(act|amendment|constitution|articles[_ ]confederation|ordinance|resolution|statute|congress)\b", blob):
        return "law_or_constitution"
    if re.search(r"\b(inaugural|address|speech|remarks|message|sermon|letter|platform)\b", blob):
        return "speech_or_argument"
    return "other_primary_text"
