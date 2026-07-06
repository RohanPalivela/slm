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

3. **Run** (the protocol default is 6 items × 3 runs over the 10 LITMUS sources):
   ```bash
   python eval/harness.py --runs 3 --n 6
   # quick smoke on 2 sources, judge off (free/fast):
   python eval/harness.py --runs 1 --limit 2 --no-judge
   # add the few-shot exemplars (ablation):
   python eval/harness.py --fewshot
   ```

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
