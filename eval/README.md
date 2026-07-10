# Eval Tools

The primary eval path is now the standalone GPU notebook:

```text
notebooks/eval_hf_gpu.ipynb
```

Use the CLI harness only for local smoke tests, local Ollama checks, or rescoring
saved generations.

## Local Harness

```bash
python3 eval/harness.py --dry-run
python3 eval/harness.py --split EVAL_HELDOUT --runs 1 --limit 2 --n 2 --no-judge
python3 eval/harness.py --split EVAL_HELDOUT --runs 3 --n 2
```

Outputs are written to `results/`, which is ignored because these files are
regenerable. Each run writes:

```text
litmus_results.md
litmus_results.json
litmus_items.jsonl
generation_attempts.json
```

`generation_attempts.json` is important when a model emits zero parsed items; it
preserves the raw generation call so parse failures do not disappear from the
metrics.

## Model Config

Copy and edit the example config when using the local harness:

```bash
cp eval/models.example.json eval/models.json
```

`eval/models.json` is ignored because local model slugs and endpoints vary by
machine. API keys should stay in environment variables.

## Core Files

| File | Role |
| :--- | :--- |
| `harness.py` | Local generation, scoring, aggregation, and report writing |
| `checks.py` / `date_utils.py` | Programmatic schema, craft, leak, and date-direction checks |
| `prompt_loader.py` | Prompt parsing and tolerant JSON extraction |
| `providers.py` | OpenAI-compatible, Ollama, Anthropic, and mock providers |
| `judge.py` | LLM judge rubric and key-valid scoring |
| `rescore_results.py` | Recompute reports from saved item outputs |
