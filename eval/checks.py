"""
Programmatic quality gates for a generated APUSH MCQ item.

These are the disqualifying checks that can be evaluated without a model. The
LLM judge (`judge.py`) covers the rest
(requires-outside-knowledge, distractor-trap validity, single-best, key validity).

Key design point (feasibility crux): the anachronism date-check is the cheap,
deterministic verifier — a CAUSE must predate the source, an EFFECT must postdate
it. This is best-effort because the prompt emits free-text `answer_dating`.
"""
from __future__ import annotations
import re

from date_utils import direction_against_source, source_year

ABSOLUTE_OR_ALLNONE = re.compile(r"\b(all|none)\s+of\s+the\s+above\b|\balways\b|\bnever\b", re.I)
PARENTHETICAL_DATE_LABEL = re.compile(
    r"\(\s*(?:c\.\s*)?(?:1[4-9]\d\d|20\d\d)"
    r"(?:\s*[-–]\s*(?:c\.\s*)?(?:\d{2,4}|present))?"
    r"\s*\)",
    re.I,
)

VALID_TRAP_TYPES = {"WRONG_ERA", "TRUE_BUT_IRRELEVANT", "SCOPE_MISMATCH", "PARTIALLY_TRUE"}

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


def _rationale_complete(item: dict) -> bool:
    rat = item.get("rationale")
    if not isinstance(rat, dict):
        return False
    return all(k in rat and str(rat.get(k, "")).strip() for k in ("A", "B", "C", "D"))


def _rationale_marks_key(item: dict) -> bool:
    idx = _answer_index(item)
    if idx is None:
        return False
    rat = item.get("rationale")
    if not isinstance(rat, dict):
        return False
    key = "ABCD"[idx]
    key_text = str(rat.get(key, "")).strip().lower()
    if not key_text:
        return False
    if key_text in {"correct", "correct."} or key_text.startswith("correct:"):
        return True
    # Treat explicit trap labels on the keyed option as a schema contradiction.
    return not any(key_text.startswith(t.lower()) for t in VALID_TRAP_TYPES)


def date_direction(item: dict, source: dict) -> str:
    """'pass' | 'fail' | 'unknown' — does the keyed answer's implied date obey the
    stem's time direction relative to the source date?"""
    src_year = source_year(source)
    arch = item.get("archetype", "")
    return direction_against_source(
        arch, item.get("answer_dating", ""), src_year,
        CAUSE_ARCHETYPES, EFFECT_ARCHETYPES,
    )


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

    traps_raw = item.get("trap_types", []) or []
    traps = [str(t).strip().upper() for t in traps_raw if str(t).strip()]
    trap_count_3 = len(traps) == 3
    trap_types_valid = bool(traps) and all(t in VALID_TRAP_TYPES for t in traps)
    trap_diversity = len(set(t for t in traps if t and t != "CORRECT")) >= 2

    # The prompt allows AT MOST ONE wrong-era distractor (rule 4/5): items that
    # lean on >=2 chronology giveaways are the dominant expert-grade failure mode
    # (the judge flags them "too chronology-driven"). This is a DISTRACTOR-CRAFT
    # gate, so it feeds expert_grade only — NOT disqualifying_ok, which gates
    # key_valid (label cleanliness). A correct answer with weak distractors is
    # still a clean, distillable label.
    wrong_era_n = sum(1 for t in traps if t == "WRONG_ERA")
    wrong_era_le1 = wrong_era_n <= 1
    no_parenthetical_option_dates = not any(PARENTHETICAL_DATE_LABEL.search(o or "") for o in opts)

    leak = source_leak(item, source)
    date = date_direction(item, source)
    rationale_complete = _rationale_complete(item)
    rationale_marks_key = _rationale_marks_key(item)

    # disqualifying_ok = label/format integrity only (feeds key_valid).
    disqualifying_ok = (four_options and one_key and no_all_none
                        and not leak and date != "fail")
    craft_ok = (trap_count_3 and trap_types_valid and trap_diversity
                and wrong_era_le1 and no_parenthetical_option_dates)
    schema_ok = rationale_complete and rationale_marks_key

    return {
        "four_options": four_options,
        "one_key": one_key,
        "no_all_none_absolute": no_all_none,
        "homogeneous_length": homogeneous,      # soft
        "trap_count_3": trap_count_3,            # craft/schema gate
        "trap_types_valid": trap_types_valid,    # craft/schema gate
        "trap_diversity_ge2": trap_diversity,    # soft
        "wrong_era_le1": wrong_era_le1,          # craft gate: bad if >=2 wrong-era traps (feeds expert_grade)
        "no_parenthetical_option_dates": no_parenthetical_option_dates,  # craft gate: date ranges in options are tells
        "rationale_complete": rationale_complete,  # schema gate
        "rationale_marks_key": rationale_marks_key,  # schema gate
        "source_leak": leak,                     # hard (bad if True)
        "date_direction": date,                  # hard if 'fail'
        "disqualifying_ok": disqualifying_ok,
        "schema_ok": schema_ok,
        "craft_ok": craft_ok and schema_ok,
    }
