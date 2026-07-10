"""
Parse prompts/litmus_generation_prompt.md into fillable SYSTEM / USER / few-shot
blocks, and provide robust JSON extraction from model responses.

The markdown structure is:  "## SYSTEM" -> fenced block ; "## USER" -> fenced
block ; "## Few-shot exemplars ..." -> fenced block (optional).
"""
from __future__ import annotations
import json
import re


def _fenced_block_after(md: str, header_substr: str) -> str | None:
    """Return the first ``` fenced block whose nearest preceding '#' header
    contains header_substr (case-insensitive)."""
    lines = md.splitlines()
    last_header = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.lstrip().startswith("#"):
            last_header = ln.lower()
        if ln.lstrip().startswith("```"):
            # collect until closing fence
            body = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                body.append(lines[i])
                i += 1
            if header_substr.lower() in last_header:
                return "\n".join(body)
        i += 1
    return None


class LitmusPrompt:
    def __init__(self, system: str, user: str, fewshot: str | None):
        self.system = system
        self.user = user
        self.fewshot = fewshot

    @classmethod
    def from_file(cls, path: str) -> "LitmusPrompt":
        with open(path, encoding="utf-8") as handle:
            md = handle.read()
        system = _fenced_block_after(md, "## system")
        user = _fenced_block_after(md, "## user")
        fewshot = _fenced_block_after(md, "few-shot")
        if not system or not user:
            raise ValueError(f"could not parse SYSTEM/USER blocks from {path}")
        return cls(system.strip(), user.strip(), (fewshot or None))

    def build(self, *, source: str, attribution: str, note: str, n: int,
              archetypes: str, difficulty: str, include_fewshot: bool) -> tuple[str, str]:
        system = self.system
        if include_fewshot and self.fewshot:
            system = system + "\n\nFEW-SHOT EXEMPLARS:\n" + self.fewshot
        user = (self.user
                .replace("{{SOURCE}}", source)
                .replace("{{ATTRIBUTION}}", attribution)
                .replace("{{NOTE}}", note or "(none)")
                .replace("{{N}}", str(n))
                .replace("{{ARCHETYPES}}", archetypes)
                .replace("{{DIFFICULTY}}", difficulty))
        return system, user


# Keys under which a model may nest the item list when it wraps the array in an
# object (e.g. {"questions": [...]}) instead of returning a bare array.
_ITEM_LIST_KEYS = ("items", "questions", "mcqs", "data", "results", "output")

# The prompt contains lower-level stem-template ids as writer guidance. Models,
# especially tuned small models, sometimes copy those into the output
# `archetype` field even though the eval contract uses the canonical archetype
# ids. Keep this mapping central so generation, repair, checks, and reports can
# score against the requested contract while preserving the model's raw label for
# debugging.
ARCHETYPE_ALIASES = {
    "cause_of": "CAUSE_OF_SOURCE",
    "effect_immediate": "EFFECT_OF_SOURCE",
    "effect_longterm": "LONGTERM_LEGACY",
    "continuation_change": "CONTINUITY_OR_CHANGE",
    "reflects_illustrates": "DEVELOPMENT_ILLUSTRATED",
    "context_response_to": "CONTEXT_SITUATION",
    "influenced_by": "CONTEXT_INFLUENCED_BY",
    "purpose_intended_to": "SOURCE_POV_PURPOSE",
    "point_of_view": "SOURCE_POV_PURPOSE",
    "evidence_supports": "EVIDENCE_SUPPORTS_CLAIM",
    "evidence_undermines": "EVIDENCE_UNDERMINES_CLAIM",
    "similar_effect": "COMPARATIVE_ANALOG",
    "differs_from": "COMPETING_INTERPRETATIONS",
}


def canonicalize_item_archetype(item: dict, requested_archetype: str | None = None) -> dict:
    """Return a shallow copy whose `archetype` is the canonical contract id.

    If `requested_archetype` is provided, it wins: each harness call asks for one
    archetype, so the item should be evaluated against that requested skill even
    if the model wrote a lower-level template id or some other label. The raw
    model-emitted value is preserved as `_model_archetype`.
    """
    out = dict(item)
    raw = out.get("archetype")
    if raw is not None and "_model_archetype" not in out:
        out["_model_archetype"] = raw
    if requested_archetype:
        out["archetype"] = requested_archetype
        out["_requested_archetype"] = requested_archetype
        return out
    if isinstance(raw, str):
        out["archetype"] = ARCHETYPE_ALIASES.get(raw.strip(), raw)
    return out


def _normalize_items(obj) -> list[dict]:
    """Coerce a parsed JSON value into a list of item dicts, honoring the contract
    that callers only ever receive dicts.

    Handles the shapes models actually emit: a bare array, a single item object,
    or a wrapper object nesting the array under a key. Any non-dict elements
    (e.g. a stray array of bare strings) are discarded rather than propagated -
    they have no schema the downstream checks/judge can use, and letting them
    through crashes the harness."""
    if isinstance(obj, dict):
        # A wrapper object like {"questions": [...]}: unwrap the first list-valued
        # candidate key, else treat the object itself as a single item.
        for key in _ITEM_LIST_KEYS:
            if isinstance(obj.get(key), list):
                return _normalize_items(obj[key])
        return [obj]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def extract_items(text: str) -> list[dict]:
    """Tolerantly pull a JSON array (or object) of items out of a model response
    that may include prose or ```json fences. Always returns a list of dicts."""
    if not text:
        return []
    t = text.strip()
    # strip a leading/trailing code fence if present
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # fast path
    try:
        return _normalize_items(json.loads(t))
    except json.JSONDecodeError:
        pass
    # scan for the first balanced [...] or {...}
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = t.find(open_ch)
        if start == -1:
            continue
        depth, in_str, esc = 0, False, False
        for j in range(start, len(t)):
            c = t[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    cand = t[start:j + 1]
                    try:
                        return _normalize_items(json.loads(cand))
                    except json.JSONDecodeError:
                        break
    return []


def _delimiter_balance(text: str) -> tuple[int, int]:
    """Return square- and curly-bracket balance while ignoring JSON strings."""
    square = curly = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
    return square, curly


def generation_format_diagnostics(text: str) -> dict:
    """Classify strict product-format reliability without repairing the output.

    Tolerant parsing remains useful for semantic diagnostics, but the primary
    product contract is one top-level JSON array. This function keeps those two
    questions separate and names the malformed object-plus-trailing-bracket shape
    observed in the v3 tuned run.
    """
    raw = text or ""
    stripped = raw.strip()
    fenced = bool(re.match(r"^```", stripped))
    no_fence = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
    no_fence = re.sub(r"\s*```$", "", no_fence).strip()
    strict_value = None
    strict_json = False
    try:
        strict_value = json.loads(no_fence)
        strict_json = True
    except (json.JSONDecodeError, TypeError):
        pass
    square_balance, curly_balance = _delimiter_balance(no_fence)
    starts_array = no_fence.startswith("[")
    starts_object = no_fence.startswith("{")
    ends_array = no_fence.endswith("]")
    ends_object = no_fence.endswith("}")
    trailing_array_bracket = bool(
        starts_object
        and ends_array
        and square_balance == -1
        and curly_balance == 0
    )
    tolerant_items = extract_items(raw)
    if not stripped:
        bucket = "empty"
    elif fenced and strict_json and isinstance(strict_value, list):
        bucket = "markdown_fenced_array"
    elif strict_json and isinstance(strict_value, list):
        bucket = "strict_array"
    elif strict_json and isinstance(strict_value, dict):
        bucket = "strict_object"
    elif trailing_array_bracket:
        bucket = "object_with_trailing_array_bracket"
    elif tolerant_items and (square_balance > 0 or curly_balance > 0):
        bucket = "complete_item_then_unclosed_trailing_output"
    elif square_balance > 0 or curly_balance > 0:
        bucket = "truncated_or_unclosed"
    elif tolerant_items:
        bucket = "tolerant_only"
    else:
        bucket = "invalid_json"
    return {
        "bucket": bucket,
        "strict_json": strict_json,
        "strict_array_contract": bool(
            strict_json and isinstance(strict_value, list) and not fenced
        ),
        "top_level_type": type(strict_value).__name__ if strict_json else None,
        "tolerant_item_count": len(tolerant_items),
        "starts_array": starts_array,
        "starts_object": starts_object,
        "ends_array": ends_array,
        "ends_object": ends_object,
        "square_balance": square_balance,
        "curly_balance": curly_balance,
        "contains_markdown_fence": fenced,
        "contains_think_tag": "<think" in raw.lower() or "</think" in raw.lower(),
    }
