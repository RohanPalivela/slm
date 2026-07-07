"""
Key-verifier for the generation pipeline (SC-KEY, docs/plan_v2 §7).

The judge grades item QUALITY; it does not independently re-derive the answer, so
it can bless a confidently-wrong or ambiguous key. Distilling wrong answers is the
worst failure mode (the student learns to be confidently incorrect), so before an
item is kept we have a SECOND model — a different family than the teacher that
wrote it — actually SOLVE the item k times with no access to the rationale. If the
independent solver doesn't reliably land on the keyed letter, the key is wrong or
the item is ambiguous: trash it.
"""
from __future__ import annotations
import collections
import json
import re

import providers

SOLVER_SYSTEM = """You are an expert AP U.S. History student taking the exam. Read \
the SOURCE and the multiple-choice question and choose the SINGLE best answer using \
the source plus your own historical knowledge. Think briefly, then commit.

Return ONLY a JSON object: {"answer": "A|B|C|D", "confidence": 0.0-1.0}. No prose."""

SOLVER_USER_TMPL = """SOURCE ({attribution}):
\"\"\"
{source_text}
\"\"\"

QUESTION: {stem}
{options}

Which single option is best? Return ONLY {{"answer": "A|B|C|D", "confidence": n}}."""

_LETTER = re.compile(r"[ABCD]")


def _fmt_options(opts):
    return "\n".join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(opts or []) if i < 4)


def _parse_letter(raw: str):
    """Pull the chosen letter from the solver's reply (JSON preferred, regex fallback)."""
    if not raw:
        return None
    try:
        obj = json.loads(re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw.strip()))
        if isinstance(obj, dict) and obj.get("answer"):
            m = _LETTER.search(str(obj["answer"]).upper())
            if m:
                return m.group(0)
    except json.JSONDecodeError:
        pass
    m = _LETTER.search((raw or "").upper())
    return m.group(0) if m else None


def solve_item(cfg: dict, source: dict, item: dict, temperature: float = 0.3) -> str | None:
    """Independently answer the item (no rationale shown). Returns 'A'..'D' or None."""
    user = SOLVER_USER_TMPL.format(
        attribution=source.get("attribution", ""),
        source_text=source.get("text", ""),
        stem=item.get("stem", ""),
        options=_fmt_options(item.get("options", [])),
    )
    try:
        raw = providers.generate(cfg, SOLVER_SYSTEM, user, temperature, role="verifier")
    except providers.ProviderError:
        return None
    return _parse_letter(raw)


def verify_item(cfg: dict, source: dict, item: dict, *, n: int = 3,
                threshold: float = 0.67, temperature: float = 0.3) -> dict:
    """Solve the item n times and check agreement with the keyed answer.

    verified = the keyed letter is the plurality choice AND wins at least
    `threshold` of the n solves. That catches both wrong keys (solver favors a
    different letter) and ambiguous items (no letter reaches threshold)."""
    key = str(item.get("answer", "")).strip().upper()[:1]
    votes = collections.Counter()
    for _ in range(n):
        letter = solve_item(cfg, source, item, temperature)
        if letter:
            votes[letter] += 1
    total = sum(votes.values())
    key_votes = votes.get(key, 0)
    agreement = (key_votes / total) if total else 0.0
    top = votes.most_common(1)[0][0] if votes else None
    verified = bool(total and top == key and agreement >= threshold)
    return {
        "verified": verified,
        "key": key,
        "agreement": round(agreement, 3),
        "votes": dict(votes),
        "n_solved": total,
    }
