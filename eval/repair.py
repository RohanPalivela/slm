"""
Generate -> repair pass for the litmus harness.

The dominant expert-grade failure mode (see results/litmus_results.md) is NOT the
key - teacher keys are ~99% historically correct - it is DISTRACTOR CRAFT: too
many options a good student eliminates in one second because they are obviously
from another era (>=2 WRONG_ERA traps) or otherwise not period-plausible.

Since the label is already clean, a cheap, targeted second pass that rewrites
ONLY the distractors (holding the stem, the keyed answer text, and the archetype
fixed) should lift expert-grade without touching correctness. Enable with
`--repair`; each generated item then costs one extra model call by the SAME model
that wrote it (so candidate-vs-teacher stays an apples-to-apples comparison of
"model + repair loop").
"""
from __future__ import annotations

import providers
from prompt_loader import extract_items

REPAIR_SYSTEM = """You are a senior AP U.S. History item writer revising the \
DISTRACTORS of a stimulus-based multiple-choice question. The stem is good and the \
keyed answer is correct - DO NOT change the stem, the keyed answer's option text, \
the archetype, or which letter is correct. Only rewrite the THREE wrong options so \
the item becomes expert-grade.

Fix these specific, common defects:
1. GIVEAWAY WRONG-ERA distractors. Each wrong option must be a real, era-plausible
   development a knowledgeable-but-imperfect student would SERIOUSLY consider. Apply
   the one-second test: if a well-prepared student can eliminate an option instantly
   purely because it is obviously from a different century or an obviously different
   topic, it is a giveaway - replace it with a closer, more tempting development
   (ideally the adjacent period AND same theme).
2. TOO MANY CHRONOLOGY TRAPS. At MOST ONE distractor may be a WRONG_ERA trap. The
   other two must be same-era traps: TRUE_BUT_IRRELEVANT (right era, wrong
   theme/mechanism), SCOPE_MISMATCH (too broad/narrow), or PARTIALLY_TRUE (one
   clause accurate, one wrong / right topic wrong direction). The three distractors
   must span at least TWO distinct trap types.
3. TELLS. Keep all four options the same category, similar length and grammar; the
   key must not be the longest or most-qualified. No "all/none of the above", no
   "always/never". Do not put parenthetical year labels or date ranges in option
   text, such as "The Cold War (1947-1991)"; dates belong in answer_dating and
   rationales, not as answer-choice tells.

Every distractor must remain factually real history for its era, wrong for exactly
ONE nameable reason, and its rationale must name that trap. The `trap_types` array
must contain exactly 3 ids chosen only from WRONG_ERA, TRUE_BUT_IRRELEVANT,
SCOPE_MISMATCH, and PARTIALLY_TRUE. The rationale object must contain all four
keys A/B/C/D, and the keyed option's rationale must be exactly "correct". Keep the
keyed answer uniquely best.

Return ONLY the full item as a single JSON object in the SAME schema you received
(archetype, period, theme, stem, options, answer, answer_dating, rationale,
trap_types, requires_outside_knowledge). No prose before or after."""

REPAIR_USER_TMPL = """SOURCE ({attribution}):
\"\"\"
{source_text}
\"\"\"

CURRENT ITEM (keep stem + keyed answer; rewrite only the weak distractors):
{item_json}

Return the revised item as ONE JSON object."""


def build_repair_prompt(source: dict, item: dict) -> tuple[str, str]:
    import json
    # Strip harness-internal keys before showing the item back to the model.
    clean = {k: v for k, v in item.items() if not k.startswith("_")}
    user = REPAIR_USER_TMPL.format(
        attribution=source.get("attribution", ""),
        source_text=source.get("text", ""),
        item_json=json.dumps(clean, ensure_ascii=False, indent=2),
    )
    return REPAIR_SYSTEM, user


def _valid_shape(it: dict, original: dict) -> bool:
    """A repaired item must keep the same 4-option shape and the SAME keyed letter
    (the whole contract is that only distractors change). Otherwise we distrust it
    and fall back to the original."""
    if not isinstance(it, dict):
        return False
    opts = it.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        return False
    if str(it.get("answer", "")).strip().upper()[:1] != str(original.get("answer", "")).strip().upper()[:1]:
        return False
    # The repair prompt promises to hold all of these fixed. Enforce that
    # promise in code; otherwise a "distractor repair" can silently rewrite the
    # question or keyed fact and invalidate the earlier provenance.
    if str(it.get("archetype", "")).strip() != str(original.get("archetype", "")).strip():
        return False
    if str(it.get("stem", "")).strip() != str(original.get("stem", "")).strip():
        return False
    key_idx = "ABCD".index(str(original.get("answer", "")).strip().upper()[:1])
    original_opts = original.get("options") or []
    if len(original_opts) != 4 or str(opts[key_idx]).strip() != str(original_opts[key_idx]).strip():
        return False
    return True


def repair_item_with_trace(
    cfg: dict,
    source: dict,
    item: dict,
    temperature: float,
    role: str = "",
) -> tuple[dict, dict]:
    """Return the repaired item plus the raw repair decision trace."""
    system, user = build_repair_prompt(source, item)
    try:
        raw = providers.generate(cfg, system, user, temperature, role=role)
    except providers.ProviderError as exc:
        return item, {
            "accepted": False,
            "reason": "provider_error",
            "error": str(exc),
            "raw": "",
            "parsed_item_count": 0,
        }
    parsed = extract_items(raw)
    if not parsed:
        return item, {
            "accepted": False,
            "reason": "unparseable_response",
            "error": None,
            "raw": raw,
            "parsed_item_count": 0,
        }
    if not _valid_shape(parsed[0], item):
        return item, {
            "accepted": False,
            "reason": "shape_or_fixed_field_contract_failed",
            "error": None,
            "raw": raw,
            "parsed_item_count": len(parsed),
        }
    repaired = parsed[0]
    # Preserve harness-internal bookkeeping and mark the item as repaired.
    for k, v in item.items():
        if k.startswith("_"):
            repaired[k] = v
    repaired["_repaired"] = True
    return repaired, {
        "accepted": True,
        "reason": "accepted",
        "error": None,
        "raw": raw,
        "parsed_item_count": len(parsed),
    }


def repair_item(cfg: dict, source: dict, item: dict, temperature: float, role: str = "") -> dict:
    """Return a repaired copy, falling back to the original on any failure."""
    repaired, _trace = repair_item_with_trace(cfg, source, item, temperature, role)
    return repaired
