#!/usr/bin/env python3
"""
Litmus harness — Deliverable 2 build-gate for the APUSH notes/source -> questions SLM.

Runs the maximal litmus prompt (prompts/litmus_generation_prompt.md) over a fixed
set of LITMUS sources for each configured model, grades every generated item with
programmatic checks + an LLM judge, and reports pass-rate / key-valid-rate /
consistency per model, then prints the BUILD / DON'T-BUILD / RETHINK door
(docs/02 §6).

Quick start (no keys, proves the pipeline):
    python eval/harness.py --dry-run

Real run (after editing eval/models.json and exporting API keys):
    python eval/harness.py --models eval/models.json --runs 3 --n 6

See eval/README.md.
"""
from __future__ import annotations
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import providers          # noqa: E402
import checks             # noqa: E402
import judge              # noqa: E402
from prompt_loader import LitmusPrompt, extract_items  # noqa: E402

DEFAULT_ARCHETYPES = "CAUSE_OF_SOURCE, EFFECT_OF_SOURCE"  # v1 causation subset (docs/03)
DIFFICULTY = "operational / test-day"


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_sources(split_name):
    splits = json.load(open(os.path.join(ROOT, "data", "splits.json"), encoding="utf-8"))
    ids = splits["splits"][split_name]["source_ids"]
    by_id = {s["id"]: s for s in load_jsonl(os.path.join(ROOT, "data", "seed_stimuli.jsonl"))}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"splits.json references unknown source ids: {missing}")
    return [by_id[i] for i in ids]


def dry_run_models():
    return {
        "candidates": [{"name": "qwen3-4b (mock)", "provider": "mock", "model": "mock"}],
        "teacher": {"name": "frontier-teacher (mock)", "provider": "mock", "model": "mock"},
        "judge": {"name": "judge (mock)", "provider": "mock", "model": "mock"},
    }


def score_item(item, source, judge_cfg, role, no_judge):
    prog = checks.run_checks(item, source)
    if no_judge:
        j = None
        eg = None  # unmeasured — cannot certify expert-grade without the judge
        kv = None
    else:
        j = judge.judge_item(judge_cfg, source, item, role=role)
        eg = judge.expert_grade(prog["disqualifying_ok"], j)
        kv = j["key_valid"] and prog["disqualifying_ok"]
    return {"prog": prog, "judge": j, "expert_grade": eg, "key_valid": kv}


def run_model(model_cfg, role, sources, prompt, judge_cfg, *, n, runs, temperature,
              include_fewshot, no_judge, limit):
    """Return a list of per-run records; each record is a list of scored items."""
    per_run = []
    srcs = sources[:limit] if limit else sources
    for r in range(runs):
        run_items = []
        for src in srcs:
            system, user = prompt.build(
                source=src["text"], attribution=src.get("attribution", ""),
                note="", n=n, archetypes=DEFAULT_ARCHETYPES, difficulty=DIFFICULTY,
                include_fewshot=include_fewshot)
            try:
                raw = providers.generate(model_cfg, system, user, temperature, role=role)
            except providers.ProviderError as e:
                print(f"    ! {model_cfg['name']} gen failed on {src['id']}: {e}", file=sys.stderr)
                continue
            items = extract_items(raw)
            for it in items:
                it["_source_id"] = src["id"]
                scored = score_item(it, src, judge_cfg, role, no_judge)
                run_items.append({"item": it, **scored})
            time.sleep(0.0 if model_cfg.get("provider") == "mock" else 0.3)
        per_run.append(run_items)
        print(f"    run {r + 1}/{runs}: {len(run_items)} items")
    return per_run


def _rate(items, key):
    vals = [x[key] for x in items if x[key] is not None]
    return (sum(1 for v in vals if v) / len(vals)) if vals else None


def aggregate(per_run):
    flat = [x for run in per_run for x in run]
    n = len(flat)
    run_pass = [p for p in (_rate(run, "expert_grade") for run in per_run if run) if p is not None]
    dims = ["spec_adherence", "distractor_craft", "outside_knowledge_skill_fit"]
    judged = [x["judge"] for x in flat if x["judge"] is not None]
    by_arch = {}
    for x in flat:
        a = x["item"].get("archetype", "?")
        by_arch.setdefault(a, []).append(x)
    return {
        "n_items": n,
        "pass_rate": _rate(flat, "expert_grade"),
        "key_valid_rate": _rate(flat, "key_valid"),
        "consistency_std": statistics.pstdev(run_pass) if len(run_pass) > 1 else 0.0,
        "run_pass_rates": [round(p, 3) for p in run_pass],
        "date_fail_rate": (sum(1 for x in flat if x["prog"]["date_direction"] == "fail") / n) if n else 0.0,
        "source_leak_rate": (sum(1 for x in flat if x["prog"]["source_leak"]) / n) if n else 0.0,
        "mean_dims": {d: (round(statistics.mean(j[d] for j in judged), 2) if judged else None) for d in dims},
        "by_archetype": {a: _rate(v, "expert_grade") for a, v in by_arch.items()},
    }


def decide(best_small, s_frontier, teacher_kv, no_judge):
    """docs/02 §6 decision matrix."""
    if no_judge:
        return "INCONCLUSIVE (judge off)", "Programmatic checks only — expert-grade and key_valid are unmeasured. Re-run with a judge configured for a real verdict."
    if best_small is not None and best_small >= 0.80:
        return "DON'T BUILD", "A prompted small model already clears >=80% expert-grade; ship a prompt, not a fine-tune."
    if teacher_kv is not None and teacher_kv < 0.70:
        return "RETHINK", "Frontier teacher key_valid_rate <70%: no clean labels to distill. Reframe (richer sources / candidate-set grounding / repair-an-item output)."
    if s_frontier is not None and s_frontier < 0.50:
        return "RETHINK", "Even the frontier teacher can't reliably produce expert-grade items (<50%)."
    if s_frontier is not None and s_frontier >= 0.70 and best_small is not None and best_small <= 0.55:
        return "BUILD (distill)", "Teacher can (>=70%), prompted small can't (<=55%): the exact gap QLoRA distillation closes. Target regime."
    if best_small is not None and 0.45 < best_small < 0.80:
        return "BUILD (narrow first)", "Promising but shaky small-model prompt; scope to the highest-gap archetypes and distill."
    return "INCONCLUSIVE", "Numbers don't match a clean door; inspect per-archetype gaps and re-run with more items."


def write_report(results, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"meta": meta, "results": results},
              open(os.path.join(out_dir, "litmus_results.json"), "w"), indent=2)

    small = {k: v for k, v in results.items() if v["role"] == "candidate"}
    teacher = next((v for v in results.values() if v["role"] == "teacher"), None)
    small_pass = [v["agg"]["pass_rate"] for v in small.values() if v["agg"]["pass_rate"] is not None]
    best_small = max(small_pass) if small_pass else None
    s_front = teacher["agg"]["pass_rate"] if teacher else None
    teacher_kv = teacher["agg"]["key_valid_rate"] if teacher else None
    door, why = decide(best_small, s_front, teacher_kv, meta["no_judge"])

    def pct(x):
        return "n/a" if x is None else f"{x:.0%}"

    L = []
    L.append("# Litmus Results (Deliverable 2b)\n")
    L.append(f"> Generated by `eval/harness.py` on {meta['timestamp']}. "
             f"Scope: {meta['archetypes']} on split `{meta['split']}` "
             f"({meta['n_sources']} sources x {meta['n']} items x {meta['runs']} runs)."
             + (" **DRY-RUN (mock models — numbers are not real).**" if meta["dry_run"] else "")
             + (" **PROGRAMMATIC-ONLY (no judge).**" if meta["no_judge"] else "") + "\n")
    L.append(f"## Decision: **{door}**\n\n{why}\n")
    L.append("| Model | Role | Items | Expert-grade | key_valid | Consistency (std) | date-fail | leak |")
    L.append("| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, v in results.items():
        a = v["agg"]
        L.append(f"| {name} | {v['role']} | {a['n_items']} | {pct(a['pass_rate'])} | "
                 f"{pct(a['key_valid_rate'])} | {a['consistency_std']:.03f} | "
                 f"{a['date_fail_rate']:.0%} | {a['source_leak_rate']:.0%} |")
    L.append("")
    L.append("### Per-archetype expert-grade pass rate")
    L.append("| Model | " + " | ".join(sorted({a for v in results.values() for a in v["agg"]["by_archetype"]})) + " |")
    archs = sorted({a for v in results.values() for a in v["agg"]["by_archetype"]})
    L.append("| :--- | " + " | ".join("---:" for _ in archs) + " |")
    for name, v in results.items():
        row = [pct(v['agg']['by_archetype'].get(a)) for a in archs]
        L.append(f"| {name} | " + " | ".join(row) + " |")
    L.append("")
    L.append("### Gate reference (docs/02 §6)")
    L.append("- **P1** teacher expert-grade >=70% AND key_valid >=70-75%  |  "
             "**P2** best prompted small <=45-55%  |  **DON'T BUILD** if small >=80%.")
    L.append(f"\n_best prompted small pass = {pct(best_small)}_ · "
             f"_teacher pass = {pct(s_front)}_ · _teacher key_valid = {pct(teacher_kv)}_")
    md_path = os.path.join(out_dir, "litmus_results.md")
    open(md_path, "w").write("\n".join(L) + "\n")
    return md_path, door, why


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="use mock models (no keys/network)")
    ap.add_argument("--models", default=os.path.join(HERE, "models.json"), help="model config JSON")
    ap.add_argument("--split", default="LITMUS")
    ap.add_argument("--n", type=int, default=6, help="items requested per source")
    ap.add_argument("--runs", type=int, default=3, help="repeats per model (consistency)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--fewshot", action="store_true", help="include the few-shot exemplar block")
    ap.add_argument("--no-judge", action="store_true", help="programmatic checks only (fast/free)")
    ap.add_argument("--limit", type=int, default=0, help="limit number of sources (quick test)")
    ap.add_argument("--out", default=os.path.join(ROOT, "results"))
    ap.add_argument("--check", action="store_true",
                    help="ping every configured model with a trivial prompt and exit")
    args = ap.parse_args()

    if args.check:
        models = json.load(open(args.models)) if os.path.exists(args.models) else dry_run_models()
        roster = [("candidate", m) for m in models.get("candidates", [])]
        for r in ("teacher", "judge"):
            if models.get(r):
                roster.append((r, models[r]))
        ok = True
        for role, cfg in roster:
            try:
                out = providers.generate(cfg, "You are a test.", "Reply with the single word: OK",
                                         temperature=0.0, role=role)
                snippet = (out or "").strip().replace("\n", " ")[:40]
                print(f"  [OK]   {role:9} {cfg['name']:22} -> {snippet!r}")
            except Exception as e:  # noqa: BLE001
                ok = False
                print(f"  [FAIL] {role:9} {cfg['name']:22} -> {e}")
        raise SystemExit(0 if ok else 1)

    if args.dry_run:
        models = dry_run_models()
        args.runs = min(args.runs, 2)
    else:
        if not os.path.exists(args.models):
            raise SystemExit(f"model config not found: {args.models} (copy eval/models.example.json)")
        models = json.load(open(args.models))

    prompt = LitmusPrompt.from_file(os.path.join(ROOT, "prompts", "litmus_generation_prompt.md"))
    sources = load_sources(args.split)
    judge_cfg = models.get("judge")
    if not args.no_judge and not judge_cfg:
        raise SystemExit("no 'judge' model configured; add one or pass --no-judge")

    roster = [("candidate", m) for m in models.get("candidates", [])]
    if models.get("teacher"):
        roster.append(("teacher", models["teacher"]))
    if not roster:
        raise SystemExit("no models to run (need 'candidates' and/or 'teacher')")

    results = {}
    for role, cfg in roster:
        print(f"[{role}] {cfg['name']}")
        per_run = run_model(cfg, role, sources, prompt, judge_cfg,
                            n=args.n, runs=args.runs, temperature=args.temperature,
                            include_fewshot=args.fewshot, no_judge=args.no_judge,
                            limit=args.limit)
        results[cfg["name"]] = {"role": role, "agg": aggregate(per_run)}

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": args.split, "n": args.n, "runs": args.runs,
        "n_sources": len(sources[:args.limit] if args.limit else sources),
        "archetypes": DEFAULT_ARCHETYPES, "dry_run": args.dry_run,
        "no_judge": args.no_judge, "fewshot": args.fewshot,
    }
    md_path, door, why = write_report(results, meta, args.out)
    print("\n" + "=" * 70)
    print(f"DECISION: {door}\n  {why}")
    print(f"report: {md_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
