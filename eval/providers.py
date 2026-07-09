"""
Model providers for the litmus harness. API providers use stdlib urllib; the
optional hf_local provider lazy-imports Transformers/PEFT only when selected.

Supported provider types (set per-model in eval/models.json):
  - "openai"            : OpenAI /v1/chat/completions   (env OPENAI_API_KEY)
  - "openai_compatible" : any OpenAI-compatible server (vLLM/Ollama/Together/…)
                          set "base_url"; api key from "api_key_env" (optional)
  - "anthropic"         : Anthropic /v1/messages        (env ANTHROPIC_API_KEY)
  - "hf_local"          : local Hugging Face Transformers model, optionally with
                          a PEFT/LoRA adapter; intended for notebook GPU evals
  - "mock"              : offline canned output for --dry-run (no network/keys)

A model config is a dict:
  {"name","provider","model","base_url"?,"api_key_env"?,"max_tokens"?}
"""
from __future__ import annotations
import json
import os
import re
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
    """OpenAI /v1/chat/completions and any OpenAI-compatible gateway (e.g. a
    router that fronts both OpenAI and Anthropic). Adapts to model quirks:
    GPT-5.x variants may reject a non-default `temperature` and/or require
    `max_completion_tokens` instead of `max_tokens`."""
    base = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
    needs_key = "api.openai.com" in base or ".com/" in base or base.startswith("https://")
    is_local = "localhost" in base or "127.0.0.1" in base or "0.0.0.0" in base
    key = os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"), "")
    if not key and needs_key and not is_local:
        raise ProviderError(f"missing API key env {cfg.get('api_key_env', 'OPENAI_API_KEY')}")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    # optional system suffix (e.g. " /no_think" to disable Qwen3 thinking mode)
    system = system + cfg.get("system_suffix", "")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    token_param = cfg.get("token_param", "max_tokens")   # some models: "max_completion_tokens"
    max_toks = cfg.get("max_tokens", 4096)
    temp = cfg.get("temperature", temperature)
    include_temp = cfg.get("include_temperature", True)

    for _ in range(3):
        payload = {"model": cfg["model"], "messages": msgs, token_param: max_toks}
        if include_temp:
            payload["temperature"] = temp
        try:
            resp = _post(base + "/chat/completions", headers, payload)
        except ProviderError as e:
            s = str(e).lower()
            if "http 400" in s and "temperature" in s and include_temp:
                include_temp = False           # retry without temperature
                continue
            if "http 400" in s and "max_tokens" in s and token_param == "max_tokens":
                token_param = "max_completion_tokens"  # retry with the newer field
                continue
            raise
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        return msg.get("content") or ""
    raise ProviderError("exhausted parameter adaptations (400s on temperature/max_tokens)")


def _call_ollama(cfg: dict, system: str, user: str, temperature: float) -> str:
    """Native Ollama /api/chat. Unlike the OpenAI-compat path, this can disable
    Qwen3 'thinking' (think:false) and keep the model warm (keep_alive) so it does
    not cold-reload between sources."""
    base = cfg.get("base_url", "http://localhost:11434").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    options = {"temperature": cfg.get("temperature", temperature),
               "num_predict": cfg.get("max_tokens", 4096)}
    if cfg.get("num_ctx"):
        options["num_ctx"] = cfg["num_ctx"]      # fit prompt + generation
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system + cfg.get("system_suffix", "")},
                     {"role": "user", "content": user}],
        "think": cfg.get("think", False),
        "stream": False,
        "keep_alive": cfg.get("keep_alive", "15m"),
        "options": options,
    }
    if cfg.get("format"):                          # e.g. "json" -> constrain to valid JSON, no rambling
        payload["format"] = cfg["format"]
    resp = _post(base + "/api/chat", {"Content-Type": "application/json"}, payload)
    return (resp.get("message") or {}).get("content") or ""


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


# ------------------------ local Hugging Face / PEFT ------------------------

_HF_LOCAL = {"key": None, "tokenizer": None, "model": None}


def _clear_hf_local() -> None:
    _HF_LOCAL.update({"key": None, "tokenizer": None, "model": None})
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _torch_dtype(torch, name: str):
    if name == "auto":
        return "auto"
    return {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }.get(str(name).lower(), torch.float16)


def _load_hf_local(cfg: dict):
    """Load exactly one local HF model at a time. Keeping both base and tuned
    4B models resident can exceed Colab/T4 VRAM, so switching configs clears the
    previous model before loading the next one."""
    key = json.dumps({
        "model": cfg["model"],
        "adapter": cfg.get("adapter"),
        "load_in_4bit": cfg.get("load_in_4bit", True),
        "torch_dtype": cfg.get("torch_dtype", "float16"),
        "device_map": cfg.get("device_map", "auto"),
    }, sort_keys=True)
    if _HF_LOCAL["key"] == key:
        return _HF_LOCAL["tokenizer"], _HF_LOCAL["model"]

    _clear_hf_local()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:
        raise ProviderError(
            "hf_local provider needs transformers + torch. In the notebook, run: "
            "pip install -U transformers accelerate peft bitsandbytes"
        ) from e

    model_id = cfg["model"]
    adapter_id = cfg.get("adapter")
    tokenizer_id = cfg.get("tokenizer") or adapter_id or model_id
    token_env = cfg.get("hf_token_env", "HF_TOKEN")
    token = os.environ.get(token_env) or None
    common = {"token": token, "trust_remote_code": cfg.get("trust_remote_code", True)}

    try:
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_id, **common)
    except Exception:
        if tokenizer_id == model_id:
            raise
        tokenizer = AutoTokenizer.from_pretrained(model_id, **common)
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = _torch_dtype(torch, cfg.get("torch_dtype", "float16"))
    model_kwargs = {
        **common,
        "device_map": cfg.get("device_map", "auto"),
        "torch_dtype": dtype,
    }
    if cfg.get("load_in_4bit", True):
        try:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype if dtype != "auto" else torch.float16,
                bnb_4bit_quant_type=cfg.get("bnb_4bit_quant_type", "nf4"),
                bnb_4bit_use_double_quant=cfg.get("bnb_4bit_use_double_quant", True),
            )
        except Exception as e:
            raise ProviderError(
                "load_in_4bit=True requires bitsandbytes. Either install it or set "
                "'load_in_4bit': false in the hf_local model config."
            ) from e

    model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)
    if adapter_id:
        try:
            from peft import PeftModel
        except Exception as e:
            raise ProviderError("hf_local adapter configs require peft.") from e
        model = PeftModel.from_pretrained(model, adapter_id, token=token)
    model.eval()

    _HF_LOCAL.update({"key": key, "tokenizer": tokenizer, "model": model})
    return tokenizer, model


def _apply_chat_template(tokenizer, messages: list[dict], think: bool) -> str:
    kwargs = {"tokenize": False, "add_generation_prompt": True}
    try:
        return tokenizer.apply_chat_template(messages, enable_thinking=think, **kwargs)
    except TypeError:
        return tokenizer.apply_chat_template(messages, **kwargs)


def _call_hf_local(cfg: dict, system: str, user: str, temperature: float) -> str:
    tokenizer, model = _load_hf_local(cfg)
    try:
        import torch
    except Exception as e:
        raise ProviderError("hf_local provider needs torch.") from e

    messages = [
        {"role": "system", "content": system + cfg.get("system_suffix", "")},
        {"role": "user", "content": user},
    ]
    prompt = _apply_chat_template(tokenizer, messages, bool(cfg.get("think", False)))
    device = next(model.parameters()).device
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    temp = cfg.get("temperature", temperature)
    do_sample = temp is not None and float(temp) > 0
    gen_kwargs = {
        "max_new_tokens": cfg.get("max_tokens", 1536),
        "do_sample": do_sample,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = float(temp)
        if cfg.get("top_p") is not None:
            gen_kwargs["top_p"] = cfg["top_p"]
        if cfg.get("top_k") is not None:
            gen_kwargs["top_k"] = cfg["top_k"]

    with torch.inference_mode():
        out = model.generate(**inputs, **gen_kwargs)
    new_tokens = out[0, inputs["input_ids"].shape[-1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return re.sub(r"^\s*<think>\s*</think>\s*", "", text).strip()


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
    if p == "ollama":
        return _call_ollama(cfg, system, user, temperature)
    if p == "hf_local":
        return _call_hf_local(cfg, system, user, temperature)
    if p == "anthropic":
        return _call_anthropic(cfg, system, user, temperature)
    raise ProviderError(f"unknown provider {p!r} for model {cfg.get('name')!r}")
