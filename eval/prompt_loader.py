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
        md = open(path, encoding="utf-8").read()
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


def _normalize_items(obj) -> list[dict]:
    """Coerce a parsed JSON value into a list of item dicts, honoring the contract
    that callers only ever receive dicts.

    Handles the shapes models actually emit: a bare array, a single item object,
    or a wrapper object nesting the array under a key. Any non-dict elements
    (e.g. a stray array of bare strings) are discarded rather than propagated —
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
