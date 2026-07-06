# Litmus Harness (`eval/`)

Runs the **Deliverable 2 build-gate**: should the SLM be built at all? It feeds the
maximal litmus prompt over a fixed set of sources through each model, grades every
generated question (programmatic checks + LLM judge), and prints the **BUILD /
DON'T BUILD / RETHINK** door per [`../docs/02_litmus_test_prompt.md`](../docs/02_litmus_test_prompt.md).

Pure Python **standard library** — nothing to `pip install`. Python ≥ 3.9.

## 1. Prove the pipeline (no keys, no network)

```bash
python eval/harness.py --dry-run
```

This uses mock models so the full loop (parse prompt → generate → programmatic
checks → judge → aggregate → decision) runs end to end and writes
`results/litmus_results.{json,md}`. The numbers are fake; it only proves plumbing.

## 2. Real run

1. **Serve / choose models.** Copy the config and edit it:
   ```bash
   cp eval/models.example.json eval/models.json
   ```
   - `candidates`: the small model(s) an SLM would fine-tune (e.g. Qwen3-4B-Instruct).
     Serve locally with **vLLM** or **Ollama** (both expose an OpenAI-compatible
     `/v1`), or point at a hosted endpoint. Add 0.6B/1.7B to see the size cliff.
   - `teacher`: a frontier model (the distillation ceiling).
   - `judge`: a **different family** than teacher/candidates (so it doesn't grade
     its own work).
   Update the model slugs to current versions.

2. **Export API keys** (names must match `api_key_env` in the config):
   ```bash
   export OPENAI_API_KEY=...        # judge (and/or openai candidates)
   export ANTHROPIC_API_KEY=...     # teacher
   export LOCAL_API_KEY=...         # local vLLM/Ollama (often any string)
   ```
   > Before distilling later, confirm the **teacher's Terms of Service** permit
   > generating training data for another model (see `../docs/05_data_sourcing_and_legal.md`).

3. **Check connectivity first**, then run (the protocol default is 6 items × 3
   runs over the 10 LITMUS sources):
   ```bash
   python eval/harness.py --check              # ping every model, print OK/FAIL
   python eval/harness.py --runs 3 --n 6       # the real build-gate
   # quick smoke on 2 sources, judge off (free/fast):
   python eval/harness.py --runs 1 --limit 2 --no-judge
   # add the few-shot exemplars (ablation):
   python eval/harness.py --fewshot
   ```

   **Single OpenAI-compatible gateway** (one router fronting multiple providers):
   set `provider: "openai_compatible"`, `base_url` to the gateway, `model` to the
   router slug (e.g. `claude-group/claude-opus-4-8`, `openai-group/gpt-5.5`), and
   point every `api_key_env` at the same gateway key. For GPT-5.x, if the router
   rejects params, add `"include_temperature": false` and
   `"token_param": "max_completion_tokens"` to that model's entry (the provider
   also auto-retries those two adaptations on a 400).

   **Run Qwen3-4B locally with Ollama** (easiest on a Mac/PC):
   ```bash
   # install: https://ollama.com/download   (or: brew install ollama)
   ollama serve            # starts the server on :11434
   ollama pull qwen3:4b    # ~2.9 GB; first run downloads it
   ```
   Use the **`ollama` provider** for the candidate (not `openai_compatible`): it
   sets `think:false` (Qwen3's thinking mode otherwise burns the token budget and
   can return empty content) and `keep_alive` (so the model stays warm between
   sources instead of cold-reloading). No key needed.

   **Performance note (laptop).** qwen3:4b runs ~20 tok/s once warm. The dominant
   cost is generation length, so **`max_tokens` (num_predict) is the speed lever**:
   time ≈ `num_predict / 20`. The candidate config uses `max_tokens: 1024` +
   `format: "json"` → clean JSON, ~25–30s/source warm. Caveats:
   - the **first** source adds a one-time ~1–2 min model load;
   - Ollama serves requests **serially** — don't run two jobs at once or they
     queue and look "stuck" (this was the original "stall"); and `ollama ps`
     shows what's loaded;
   - don't raise `num_ctx` above 4096 on a small Air (memory pressure + reload);
   - `format:"json"` yields ~1 item/call, so raise `--runs` for a bigger sample.

   Smoke first, then scale:
   ```bash
   python eval/harness.py --runs 1 --limit 2 --n 2   # ~4-6 min incl. load
   python eval/harness.py --runs 3 --n 6             # full gate (~30-45 min)
   ```
   Without `format:"json"` the base model rambles for minutes before emitting
   JSON — that unreliability is real litmus signal, but for a tractable laptop run
   we constrain it. For a fast full run, point the candidate at a **hosted**
   Qwen3-4B (`provider: "openai_compatible"`, `base_url: ".../v1"`).

4. **Read the verdict.** The decision + tables land in `results/litmus_results.md`.
   Copy the summary into `docs/02b_litmus_results.md` and commit it (that's the
   canonical build-gate record the training plan depends on).

## 3. What gets measured

| Metric | Meaning |
| :--- | :--- |
| **Expert-grade pass rate** | fraction of items passing every disqualifying check (programmatic + judge) with spec-adherence = 2 |
| **key_valid** | keyed answer historically correct **and** uniquely best (the SC-KEY crux) |
| **Consistency (std)** | std of pass rate across runs — reliability, not peak |
| **date-fail / leak** | wrong-era key rate / source-echo rate (programmatic) |
| **Per-archetype** | pass rate for `CAUSE_OF_SOURCE` vs `EFFECT_OF_SOURCE` |

## 4. The decision (docs/02 §6)

- best prompted **small ≥ 80%** → **DON'T BUILD** (ship a prompt)
- **teacher ≥ 70%** & key_valid ≥ 70–75% **and** small ≤ 45–55% → **BUILD (distill)**
- **teacher key_valid < 70%** (or teacher pass < 50%) → **RETHINK** (no clean labels)

## Files

| File | Role |
| :--- | :--- |
| `harness.py` | orchestrator + metrics + decision + report writer |
| `providers.py` | OpenAI / OpenAI-compatible / Anthropic REST + mock |
| `prompt_loader.py` | parse the litmus prompt; tolerant JSON extraction |
| `checks.py` | programmatic gates (anachronism date-check, source-leak, …) |
| `judge.py` | LLM-as-judge rubric + `key_valid` + `expert_grade` |
| `models.example.json` | copy → `models.json` and edit |

Inputs: `../data/splits.json` (which sources), `../data/seed_stimuli.jsonl` (the
sources), `../prompts/litmus_generation_prompt.md` (the prompt),
`../data/apush_key_developments.json` (dates, referenced by the strict train-time
verifier).
