"""
Key-verifier for the generation pipeline.

The judge grades item QUALITY; it does not independently re-derive the answer, so
it can bless a confidently-wrong or ambiguous key. Distilling wrong answers is the
worst failure mode (the student learns to be confidently incorrect), so before an
item is kept we have a SECOND model - a different family than the teacher that
wrote it - actually SOLVE the item k times with no access to the rationale. If the
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

_EXPLICIT_LETTER = re.compile(
    r"^\s*(?:answer\s*[:=\-]?\s*)?[\[(]?([ABCD])(?:[\]).:]|\s|$)",
    re.I,
)


def _fmt_options(opts):
    return "\n".join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(opts or []) if i < 4)


def _parse_letter(raw: str):
    """Pull the chosen letter from the solver's reply (JSON preferred, regex fallback)."""
    if not raw:
        return None
    try:
        obj = json.loads(re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw.strip()))
        if isinstance(obj, dict) and obj.get("answer"):
            m = _EXPLICIT_LETTER.match(str(obj["answer"]))
            if m:
                return m.group(1).upper()
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw.strip())
    m = _EXPLICIT_LETTER.match(cleaned)
    return m.group(1).upper() if m else None


def solve_item_with_trace(
    cfg: dict,
    source: dict,
    item: dict,
    temperature: float = 0.3,
) -> tuple[str | None, dict]:
    """Independently answer the item and preserve the raw solver response."""
    user = SOLVER_USER_TMPL.format(
        attribution=source.get("attribution", ""),
        source_text=source.get("text", ""),
        stem=item.get("stem", ""),
        options=_fmt_options(item.get("options", [])),
    )
    try:
        raw = providers.generate(cfg, SOLVER_SYSTEM, user, temperature, role="verifier")
    except providers.ProviderError as exc:
        return None, {
            "answer": None,
            "raw": "",
            "error": str(exc),
            "parse_status": "provider_error",
        }
    answer = _parse_letter(raw)
    return answer, {
        "answer": answer,
        "raw": raw,
        "error": None,
        "parse_status": "ok" if answer else "unparseable",
    }


def solve_item(cfg: dict, source: dict, item: dict, temperature: float = 0.3) -> str | None:
    """Independently answer the item (no rationale shown). Returns 'A'..'D' or None."""
    answer, _trace = solve_item_with_trace(cfg, source, item, temperature)
    return answer


def verify_item(cfg: dict, source: dict, item: dict, *, n: int = 3,
                threshold: float = 1.0, temperature: float = 0.3) -> dict:
    """Solve the item n times and check agreement with the keyed answer.

    verified = the keyed letter is the plurality choice AND wins at least
    `threshold` of the n solves. That catches both wrong keys (solver favors a
    different letter) and ambiguous items (no letter reaches threshold).
    Every requested solve must return a parseable vote; missing votes fail closed."""
    key = str(item.get("answer", "")).strip().upper()[:1]
    votes = collections.Counter()
    attempts = []
    for attempt_index in range(n):
        letter, trace = solve_item_with_trace(cfg, source, item, temperature)
        trace["attempt"] = attempt_index + 1
        attempts.append(trace)
        if letter:
            votes[letter] += 1
    total = sum(votes.values())
    key_votes = votes.get(key, 0)
    agreement = (key_votes / total) if total else 0.0
    top = votes.most_common(1)[0][0] if votes else None
    verified = bool(total == n and top == key and agreement >= threshold)
    return {
        "verified": verified,
        "key": key,
        "threshold": threshold,
        "requested_solves": n,
        "agreement": round(agreement, 3),
        "votes": dict(votes),
        "n_solved": total,
        "attempts": attempts,
    }
