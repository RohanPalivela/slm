"""
Model providers for the litmus harness — stdlib only (urllib), no SDK required.

Supported provider types (set per-model in eval/models.json):
  - "openai"            : OpenAI /v1/chat/completions   (env OPENAI_API_KEY)
  - "openai_compatible" : any OpenAI-compatible server (vLLM/Ollama/Together/…)
                          set "base_url"; api key from "api_key_env" (optional)
  - "anthropic"         : Anthropic /v1/messages        (env ANTHROPIC_API_KEY)
  - "mock"              : offline canned output for --dry-run (no network/keys)

A model config is a dict:
  {"name","provider","model","base_url"?,"api_key_env"?,"max_tokens"?}
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error


class ProviderError(Exception):
    pass


def _post(url: str, headers: dict, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            last = ProviderError(f"HTTP {e.code}: {body[:500]}")
            if e.code in (429, 500, 502, 503, 529):
                time.sleep(2 * (attempt + 1))
                continue
            raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = ProviderError(f"network error: {e}")
            time.sleep(2 * (attempt + 1))
    raise last or ProviderError("unknown error")


def _call_openai(cfg: dict, system: str, user: str, temperature: float) -> str:
    base = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"), "")
    if not key and "api.openai.com" in base:
        raise ProviderError(f"missing API key env {cfg.get('api_key_env', 'OPENAI_API_KEY')}")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": cfg.get("max_tokens", 4096),
    }
    resp = _post(base + "/chat/completions", headers, payload)
    return resp["choices"][0]["message"]["content"]


def _call_anthropic(cfg: dict, system: str, user: str, temperature: float) -> str:
    key = os.environ.get(cfg.get("api_key_env", "ANTHROPIC_API_KEY"), "")
    if not key:
        raise ProviderError(f"missing API key env {cfg.get('api_key_env', 'ANTHROPIC_API_KEY')}")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "system": system,
        "max_tokens": cfg.get("max_tokens", 4096),
        "temperature": temperature,
        "messages": [{"role": "user", "content": user}],
    }
    resp = _post("https://api.anthropic.com/v1/messages", headers, payload)
    # content is a list of blocks; concatenate text blocks
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")


# --------------------------- mock (offline dry-run) -------------------------

def _mock_generation(cfg: dict, user: str, role: str) -> str:
    """Return a small, schema-valid 2-item array with dates made consistent with
    the source year (parsed from the ATTRIBUTION line) so the checks/judge
    pipeline exercises end-to-end and demonstrates the intended flow offline."""
    import re
    m = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", user)
    yr = int(m.group(1)) if m else 1850
    items = [
        {
            "archetype": "CAUSE_OF_SOURCE", "period": 5, "theme": "PCE",
            "stem": "Which of the following contributed most directly to the position expressed in the excerpt?",
            "options": [
                "A specific prior development that set the immediate context",
                "A broad long-run background condition of the era",
                "A real development from a later period",
                "A real but thematically unrelated development of the era",
            ],
            "answer": "A",
            "answer_dating": f"The keyed cause (c. {yr - 8}) predates the {yr} source, consistent with a cause.",
            "rationale": {"correct": "The specific antecedent is the most-direct cause.",
                          "A": "correct", "B": "SCOPE_MISMATCH: too broad a background condition",
                          "C": "WRONG_ERA: from a later period", "D": "TRUE_BUT_IRRELEVANT: wrong theme"},
            "trap_types": ["SCOPE_MISMATCH", "WRONG_ERA", "TRUE_BUT_IRRELEVANT"],
            "requires_outside_knowledge": "an antecedent development not stated in the source",
        },
        {
            "archetype": "EFFECT_OF_SOURCE", "period": 5, "theme": "PCE",
            "stem": "The ideas expressed in the excerpt most immediately led to which of the following?",
            "options": [
                "A specific short-term development that followed",
                "A development from the opposite direction of change",
                "A real development from a much later period",
                "A real but thematically unrelated development of the era",
            ],
            "answer": "A",
            "answer_dating": f"The keyed effect (c. {yr + 6}) postdates the {yr} source, consistent with an effect.",
            "rationale": {"correct": "The specific consequence directly followed.",
                          "A": "correct", "B": "PARTIALLY_TRUE: wrong direction",
                          "C": "WRONG_ERA: much later", "D": "TRUE_BUT_IRRELEVANT: wrong theme"},
            "trap_types": ["PARTIALLY_TRUE", "WRONG_ERA", "TRUE_BUT_IRRELEVANT"],
            "requires_outside_knowledge": "a consequence not stated in the source",
        },
    ]
    return json.dumps(items)


def generate(cfg: dict, system: str, user: str, temperature: float, role: str = "") -> str:
    p = cfg.get("provider")
    if p == "mock":
        return _mock_generation(cfg, user, role)
    if p == "openai" or p == "openai_compatible":
        return _call_openai(cfg, system, user, temperature)
    if p == "anthropic":
        return _call_anthropic(cfg, system, user, temperature)
    raise ProviderError(f"unknown provider {p!r} for model {cfg.get('name')!r}")
