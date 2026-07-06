"""
Programmatic quality gates for a generated APUSH MCQ item (litmus + train filter).

Mirrors the disqualifying `quality_checks` in taxonomy/apush_question_archetypes.json
that can be checked WITHOUT a model. The LLM-judge (judge.py) covers the rest
(requires-outside-knowledge, distractor-trap validity, single-best, key validity).

Key design point (feasibility crux): the anachronism date-check is the cheap,
deterministic verifier — a CAUSE must predate the source, an EFFECT must postdate
it. Here it is best-effort (the litmus prompt emits free-text `answer_dating`, not
a development_id); the bulk data-gen pipeline does the strict id-based version.
"""
from __future__ import annotations
import re

ABSOLUTE_OR_ALLNONE = re.compile(r"\b(all|none)\s+of\s+the\s+above\b|\balways\b|\bnever\b", re.I)
_YEAR = re.compile(r"\b(1[4-9]\d\d|20\d\d)\b")

CAUSE_ARCHETYPES = {"CAUSE_OF_SOURCE", "CONTEXT_SITUATION", "CONTEXT_INFLUENCED_BY"}
EFFECT_ARCHETYPES = {"EFFECT_OF_SOURCE", "LONGTERM_LEGACY", "COMPARATIVE_ANALOG",
                     "CONTINUITY_OR_CHANGE"}


def _strip_label(opt: str) -> str:
    return re.sub(r"^\s*[A-D][).:]?\s+", "", opt or "").strip()


def _answer_index(item: dict):
    a = str(item.get("answer", "")).strip().upper()
    if a and a[0] in "ABCD":
        return "ABCD".index(a[0])
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _years(text: str) -> list[int]:
    return [int(y) for y in _YEAR.findall(text or "")]


def _source_year(source: dict):
    y = source.get("year")
    if isinstance(y, list) and y:
        return int(y[0])
    if isinstance(y, int):
        return y
    return None


def date_direction(item: dict, source: dict) -> str:
    """'pass' | 'fail' | 'unknown' — does the keyed answer's implied date obey the
    stem's time direction relative to the source date?"""
    src_year = _source_year(source)
    arch = item.get("archetype", "")
    if src_year is None or (arch not in CAUSE_ARCHETYPES and arch not in EFFECT_ARCHETYPES):
        return "unknown"
    ys = [y for y in _years(item.get("answer_dating", "")) if y != src_year]
    if not ys:
        return "unknown"
    if arch in CAUSE_ARCHETYPES:
        # a cause should predate the source; fail if the earliest cited year is after it
        return "fail" if min(ys) > src_year else "pass"
    # effect should postdate the source; fail if the latest cited year is before it
    return "fail" if max(ys) < src_year else "pass"


def source_leak(item: dict, source: dict) -> bool:
    """True if the correct option is (nearly) a verbatim span of the source —
    i.e. the item asks the source back to itself."""
    idx = _answer_index(item)
    opts = item.get("options", [])
    if idx is None or idx >= len(opts):
        return False
    ans = _norm(_strip_label(opts[idx]))
    if len(ans) < 40:
        return False
    return ans in _norm(source.get("text", ""))


def run_checks(item: dict, source: dict) -> dict:
    """Return a dict of check_name -> result. `disqualifying_ok` summarizes the
    hard programmatic gates (the ones that alone can fail an item)."""
    opts = item.get("options", [])
    idx = _answer_index(item)
    labels = [_strip_label(o) for o in opts] if opts else []

    four_options = isinstance(opts, list) and len(opts) == 4
    one_key = idx is not None and (0 <= idx < len(opts))
    no_all_none = not any(ABSOLUTE_OR_ALLNONE.search(o or "") for o in opts)

    # homogeneous length: correct option not > 1.7x the median distractor length
    homogeneous = True
    if four_options and one_key and labels:
        distractor_lens = [len(l) for k, l in enumerate(labels) if k != idx]
        if distractor_lens:
            distractor_lens.sort()
            mid = distractor_lens[len(distractor_lens) // 2] or 1
            homogeneous = len(labels[idx]) <= 1.7 * mid

    traps = item.get("trap_types", []) or []
    trap_diversity = len(set(t for t in traps if t and t != "correct")) >= 2

    leak = source_leak(item, source)
    date = date_direction(item, source)

    disqualifying_ok = (four_options and one_key and no_all_none
                        and not leak and date != "fail")

    return {
        "four_options": four_options,
        "one_key": one_key,
        "no_all_none_absolute": no_all_none,
        "homogeneous_length": homogeneous,      # soft
        "trap_diversity_ge2": trap_diversity,    # soft
        "source_leak": leak,                     # hard (bad if True)
        "date_direction": date,                  # hard if 'fail'
        "disqualifying_ok": disqualifying_ok,
    }
