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
import concurrent.futures as cf
import json
import os
import statistics
import sys
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import providers          # noqa: E402
import checks             # noqa: E402
import judge              # noqa: E402
import repair             # noqa: E402
from prompt_loader import LitmusPrompt, extract_items, canonicalize_item_archetype  # noqa: E402

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
        nm = None
        kv = None
    else:
        j = judge.judge_item(judge_cfg, source, item, role=role)
        # expert_grade / near_miss also require the distractor-craft gate
        # (<=1 wrong-era); key_valid measures ONLY label cleanliness, so it must
        # not depend on it.
        craft_ok = prog["disqualifying_ok"] and prog.get("craft_ok", prog["wrong_era_le1"])
        eg = judge.expert_grade(craft_ok, j)
        nm = judge.near_grade(craft_ok, j)
        kv = j["key_valid"] and prog["disqualifying_ok"]
    return {"prog": prog, "judge": j, "expert_grade": eg, "near_miss": nm, "key_valid": kv}


class Progress:
    """Thread-safe single-line progress bar. Accurately reflects completed/total
    across parallel workers."""

    def __init__(self, total, label):
        self.total = max(total, 1)
        self.label = label
        self.done = 0
        self.fails = 0
        self.items = 0
        self._lock = threading.Lock()
        self._t0 = time.time()
        self._render()

    def tick(self, n_items=0, failed=False):
        with self._lock:
            self.done += 1
            self.items += n_items
            if failed:
                self.fails += 1
            self._render()

    def _render(self):
        pct = self.done / self.total
        bar_n = int(pct * 20)
        bar = "#" * bar_n + "-" * (20 - bar_n)
        el = time.time() - self._t0
        extra = f" items={self.items}" if self.items else ""
        fails = f" fails={self.fails}" if self.fails else ""
        sys.stdout.write(f"\r    {self.label:22} [{bar}] {self.done}/{self.total}"
                         f"{extra}{fails} {el:4.0f}s   ")
        sys.stdout.flush()

    def finish(self):
        with self._lock:
            self._render()
            sys.stdout.write("\n")
            sys.stdout.flush()


def _concurrency_for(cfg, gateway_default):
    """Local Ollama is served serially — parallelism there hurts. Gateway/API
    models can run concurrent requests."""
    if cfg.get("provider") in ("ollama", "mock"):
        return 1
    return int(cfg.get("concurrency", gateway_default))


def _item_complete(it):
    """Heuristic 'not truncated' check: a fully-formed item has 4 options, a keyed
    answer, and a rationale for every option. `rationale` sits near the END of the
    output schema, so its presence means the JSON object wasn't cut off mid-item.
    Lets us distinguish a real truncation from a model that simply chose to emit
    fewer (complete) items than we asked for."""
    opts = it.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        return False
    if not it.get("stem") or not it.get("answer"):
        return False
    rat = it.get("rationale")
    return isinstance(rat, dict) and all(k in rat for k in ("A", "B", "C", "D"))


def generate_all(cfg, role, sources, prompt, *, n, runs, temperature,
                 include_fewshot, limit, concurrency):
    """Parallel generation for one model. One call per (run, source, ARCHETYPE) —
    so every archetype is measured even for a model that emits a single item per
    call (e.g. a 4B under format:json, which otherwise only ever produces the first
    requested archetype). Returns raw (unjudged) records; progress is live."""
    srcs = sources[:limit] if limit else sources
    archs = [a.strip() for a in DEFAULT_ARCHETYPES.split(",") if a.strip()]
    n_per = max(1, round(n / len(archs)))
    tasks = [(r, s, a) for r in range(runs) for s in srcs for a in archs]
    prog = Progress(len(tasks), f"gen[{cfg['name']}]")
    records, lock = [], threading.Lock()
    empty = trunc = short = 0  # call classification (see warning below)

    def work(task):
        r, s, arch = task
        system, user = prompt.build(
            source=s["text"], attribution=s.get("attribution", ""), note="",
            n=n_per, archetypes=arch, difficulty=DIFFICULTY,
            include_fewshot=include_fewshot)
        try:
            raw = providers.generate(cfg, system, user, temperature, role=role)
            return r, s["id"], arch, extract_items(raw), None
        except providers.ProviderError as e:
            return r, s["id"], arch, [], str(e)

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(work, t) for t in tasks]
        for fut in cf.as_completed(futs):
            r, sid, arch, items, err = fut.result()
            with lock:
                for it in items:
                    it = canonicalize_item_archetype(it, requested_archetype=arch)
                    it["_source_id"] = sid
                    records.append({"model": cfg["name"], "role": role,
                                    "run": r, "source_id": sid, "item": it})
                if not err:
                    complete = sum(1 for it in items if _item_complete(it))
                    if len(items) == 0:
                        empty += 1
                    elif complete < len(items):
                        trunc += 1        # something came back but was cut off
                    elif complete < n_per:
                        short += 1        # complete items, just fewer than asked
            prog.tick(n_items=len(items), failed=bool(err))
    prog.finish()
    # Honest diagnostics: only call it truncation when items are actually
    # incomplete/empty; a model returning fewer COMPLETE items than requested is a
    # model choice (common for small models under format:json), not a token cap.
    if empty or trunc:
        sys.stdout.write(
            f"    WARNING [{cfg['name']}]: {trunc} call(s) truncated mid-item, "
            f"{empty} returned nothing — raise max_tokens/num_ctx or check the endpoint.\n")
    if short:
        sys.stdout.write(
            f"    note [{cfg['name']}]: {short}/{len(tasks)} call(s) returned complete but "
            f"FEWER than the {n_per} items requested (model's choice, not truncation); "
            f"coverage is valid, the sample is just smaller.\n")
    sys.stdout.flush()
    return records


def repair_all(cfg, role, records, sources_by_id, *, temperature, concurrency):
    """Optional generate->repair pass for ONE model: rewrite each item's weak
    distractors (same model that wrote it). Mutates records in place — replaces
    each `item` with its repaired version (or the original on any failure)."""
    if not records:
        return records
    prog = Progress(len(records), f"repair[{cfg['name']}]")

    def work(rec):
        src = sources_by_id[rec["source_id"]]
        rec["item"] = repair.repair_item(cfg, src, rec["item"], temperature, role=role)
        rec["item"] = canonicalize_item_archetype(
            rec["item"], requested_archetype=rec["item"].get("_requested_archetype"))
        return rec

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(work, rec) for rec in records]
        for fut in cf.as_completed(futs):
            fut.result()
            prog.tick()
    prog.finish()
    return records


def judge_all(gen_records, judge_cfg, sources_by_id, *, no_judge, concurrency):
    """Parallel judging over ALL generated items (both models at once) — this is
    the biggest speedup since each judge call is an independent gateway request."""
    prog = Progress(len(gen_records), "judge" if not no_judge else "score(no-judge)")
    out, lock = [], threading.Lock()

    def work(rec):
        src = sources_by_id[rec["source_id"]]
        scored = score_item(rec["item"], src, judge_cfg, rec["role"], no_judge)
        return {**rec, **scored}

    workers = 1 if no_judge else concurrency
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, rec) for rec in gen_records]
        for fut in cf.as_completed(futs):
            r = fut.result()
            with lock:
                out.append(r)
            prog.tick()
    prog.finish()
    return out


def _rate(items, key):
    vals = [x[key] for x in items if x[key] is not None]
    return (sum(1 for v in vals if v) / len(vals)) if vals else None


def aggregate(scored):
    """scored: flat list of judged records for ONE model (each has run,
    expert_grade, key_valid, prog, judge, item)."""
    n = len(scored)
    runs = sorted({x["run"] for x in scored})
    # The decision door is the near-miss (calibrated expert-quality) rate, so
    # consistency + per-archetype track that; expert_grade stays reported alongside.
    run_pass = [p for p in (_rate([x for x in scored if x["run"] == r], "near_miss")
                            for r in runs) if p is not None]
    dims = ["spec_adherence", "distractor_craft", "outside_knowledge_skill_fit"]
    judged = [x["judge"] for x in scored if x["judge"] is not None]
    by_arch = {}
    for x in scored:
        by_arch.setdefault(x["item"].get("archetype", "?"), []).append(x)
    return {
        "n_items": n,
        "pass_rate": _rate(scored, "expert_grade"),
        "near_miss_rate": _rate(scored, "near_miss"),
        "key_valid_rate": _rate(scored, "key_valid"),
        "consistency_std": statistics.pstdev(run_pass) if len(run_pass) > 1 else 0.0,
        "run_pass_rates": [round(p, 3) for p in run_pass],
        "date_fail_rate": (sum(1 for x in scored if x["prog"]["date_direction"] == "fail") / n) if n else 0.0,
        "source_leak_rate": (sum(1 for x in scored if x["prog"]["source_leak"]) / n) if n else 0.0,
        "craft_fail_rate": (sum(1 for x in scored if not x["prog"].get("craft_ok", True)) / n) if n else 0.0,
        "schema_fail_rate": (sum(1 for x in scored if not x["prog"].get("schema_ok", True)) / n) if n else 0.0,
        "invalid_trap_rate": (sum(1 for x in scored if not x["prog"].get("trap_types_valid", True)) / n) if n else 0.0,
        "option_date_tell_rate": (sum(1 for x in scored if not x["prog"].get("no_parenthetical_option_dates", True)) / n) if n else 0.0,
        "mean_dims": {d: (round(statistics.mean(j[d] for j in judged), 2) if judged else None) for d in dims},
        "by_archetype": {a: _rate(v, "near_miss") for a, v in by_arch.items()},
    }


def decide(best_small, s_frontier, teacher_kv, no_judge):
    """docs/02 §6 decision matrix. The pass metric is the NEAR-MISS
    (expert-quality) rate — every expert-grade gate except the strict, poorly-
    calibrated `spec_adherence==2` (see G-cal: judge–human agreement on spec was
    ~40%/negative-kappa, so it is unfit as a hard gate). key_valid still gates
    label cleanliness."""
    if no_judge:
        return "INCONCLUSIVE (judge off)", "Programmatic checks only — expert-quality and key_valid are unmeasured. Re-run with a judge configured for a real verdict."
    if best_small is not None and best_small >= 0.80:
        return "DON'T BUILD", "A prompted small model already clears >=80% expert-quality (near-miss); ship a prompt, not a fine-tune."
    if teacher_kv is not None and teacher_kv < 0.70:
        return "RETHINK", "Frontier teacher key_valid_rate <70%: no clean labels to distill. Reframe (richer sources / candidate-set grounding / repair-an-item output)."
    if s_frontier is not None and s_frontier < 0.50:
        return "RETHINK", "Even the frontier teacher can't reliably produce expert-quality items (<50% near-miss)."
    if s_frontier is not None and s_frontier >= 0.70 and best_small is not None and best_small <= 0.55:
        return "BUILD (distill)", "Teacher can (>=70% near-miss), prompted small can't (<=55%): the exact gap QLoRA distillation closes. Target regime."
    if best_small is not None and 0.45 < best_small < 0.80:
        return "BUILD (narrow first)", "Promising but shaky small-model prompt; scope to the highest-gap archetypes and distill."
    return "INCONCLUSIVE", "Numbers don't match a clean door; inspect per-archetype gaps and re-run with more items."


def write_report(results, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"meta": meta, "results": results},
              open(os.path.join(out_dir, "litmus_results.json"), "w"), indent=2)

    small = {k: v for k, v in results.items() if v["role"] == "candidate"}
    teacher = next((v for v in results.values() if v["role"] == "teacher"), None)
    # Door metric = near-miss (calibrated expert-quality), not the strict expert-grade.
    small_pass = [v["agg"]["near_miss_rate"] for v in small.values() if v["agg"].get("near_miss_rate") is not None]
    best_small = max(small_pass) if small_pass else None
    s_front = teacher["agg"].get("near_miss_rate") if teacher else None
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
             + (" **PROGRAMMATIC-ONLY (no judge).**" if meta["no_judge"] else "")
             + (" **+REPAIR pass (distractors rewritten by the same model).**" if meta.get("repair") else "") + "\n")
    L.append(f"## Decision: **{door}**\n\n{why}\n")
    L.append("| Model | Role | Items | Expert-grade | Near-miss | key_valid | Consistency (std) | craft-fail | schema-fail | invalid-trap | option-date | date-fail | leak |")
    L.append("| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, v in results.items():
        a = v["agg"]
        L.append(f"| {name} | {v['role']} | {a['n_items']} | {pct(a['pass_rate'])} | "
                 f"{pct(a.get('near_miss_rate'))} | "
                 f"{pct(a['key_valid_rate'])} | {a['consistency_std']:.03f} | "
                 f"{a['craft_fail_rate']:.0%} | {a['schema_fail_rate']:.0%} | "
                 f"{a['invalid_trap_rate']:.0%} | "
                 f"{a['option_date_tell_rate']:.0%} | "
                 f"{a['date_fail_rate']:.0%} | {a['source_leak_rate']:.0%} |")
    L.append("")
    L.append("### Per-archetype near-miss (expert-quality) pass rate")
    L.append("| Model | " + " | ".join(sorted({a for v in results.values() for a in v["agg"]["by_archetype"]})) + " |")
    archs = sorted({a for v in results.values() for a in v["agg"]["by_archetype"]})
    L.append("| :--- | " + " | ".join("---:" for _ in archs) + " |")
    for name, v in results.items():
        row = [pct(v['agg']['by_archetype'].get(a)) for a in archs]
        L.append(f"| {name} | " + " | ".join(row) + " |")
    L.append("")
    L.append("### Gate reference (docs/02 §6)")
    L.append("- The decision **door is the near-miss (expert-quality) rate**: "
             "**P1** teacher near-miss >=70% AND key_valid >=70-75%  |  "
             "**P2** best prompted small <=45-55%  |  **DON'T BUILD** if small >=80%.")
    L.append("- _Near-miss_ = passes every expert-grade gate EXCEPT the strict "
             "`spec_adherence==2`. Calibration (G-cal) showed judge–human agreement on "
             "`spec_adherence` was ~40% (negative kappa), so it is reported as a secondary "
             "quality score, not used as a hard gate. _Expert-grade_ (spec==2) is the "
             "stricter column; a big near-miss-minus-expert-grade gap is distractor polish only.")
    L.append(f"\n**Door (near-miss):** _best prompted small = {pct(best_small)}_ · "
             f"_teacher = {pct(s_front)}_ · _teacher key_valid = {pct(teacher_kv)}_ · "
             f"_teacher expert-grade (strict) = {pct(teacher['agg']['pass_rate']) if teacher else 'n/a'}_")
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
    ap.add_argument("--repair", action="store_true",
                    help="add a generate->repair pass: each item's distractors are rewritten "
                         "by the SAME model (targets the distractor-craft gap; one extra call/item)")
    ap.add_argument("--no-judge", action="store_true", help="programmatic checks only (fast/free)")
    ap.add_argument("--limit", type=int, default=0, help="limit number of sources (quick test)")
    ap.add_argument("--gen-concurrency", type=int, default=8,
                    help="parallel generation requests for gateway/API models (local Ollama stays serial)")
    ap.add_argument("--judge-concurrency", type=int, default=8,
                    help="parallel judge requests")
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

    sources_by_id = {s["id"]: s for s in sources}

    # Phase 1 — GENERATION (per model; gateway models run concurrent requests,
    # local Ollama stays serial). Two phases keep the progress UI unambiguous.
    print("Phase 1/2: generation" + (" + repair" if args.repair else ""))
    gen_records = []
    for role, cfg in roster:
        recs = generate_all(
            cfg, role, sources, prompt, n=args.n, runs=args.runs,
            temperature=args.temperature, include_fewshot=args.fewshot,
            limit=args.limit, concurrency=_concurrency_for(cfg, args.gen_concurrency))
        if args.repair:
            recs = repair_all(cfg, role, recs, sources_by_id,
                              temperature=args.temperature,
                              concurrency=_concurrency_for(cfg, args.gen_concurrency))
        gen_records += recs

    # Phase 2 — JUDGING (all items from all models judged in parallel: the big win).
    print("Phase 2/2: judging")
    scored = judge_all(gen_records, judge_cfg, sources_by_id,
                       no_judge=args.no_judge, concurrency=args.judge_concurrency)

    results = {}
    for role, cfg in roster:
        model_scored = [x for x in scored if x["model"] == cfg["name"]]
        results[cfg["name"]] = {"role": role, "agg": aggregate(model_scored)}

    item_records = []
    for x in scored:
        it = x["item"]
        item_records.append({
            "model": x["model"], "role": x["role"], "run": x["run"],
            "source_id": it.get("_source_id"), "archetype": it.get("archetype"),
            "model_archetype": it.get("_model_archetype"),
            "requested_archetype": it.get("_requested_archetype"),
            "expert_grade": x["expert_grade"], "near_miss": x["near_miss"],
            "key_valid": x["key_valid"],
            "prog": x["prog"], "judge": x["judge"],
            "stem": it.get("stem"), "options": it.get("options"),
            "answer": it.get("answer"), "answer_dating": it.get("answer_dating"),
            "rationale": it.get("rationale"), "trap_types": it.get("trap_types"),
        })

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": args.split, "n": args.n, "runs": args.runs,
        "n_sources": len(sources[:args.limit] if args.limit else sources),
        "archetypes": DEFAULT_ARCHETYPES, "dry_run": args.dry_run,
        "no_judge": args.no_judge, "fewshot": args.fewshot, "repair": args.repair,
    }
    md_path, door, why = write_report(results, meta, args.out)
    items_path = os.path.join(args.out, "litmus_items.jsonl")
    with open(items_path, "w", encoding="utf-8") as f:
        for rec in item_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("\n" + "=" * 70)
    print(f"DECISION: {door}\n  {why}")
    print(f"report:      {md_path}")
    print(f"per-item:    {items_path}   (each item + judge reasoning; read to see WHY items failed)")
    if meta["n_sources"] * meta["runs"] < 8:
        print("NOTE: tiny sample + uncalibrated judge -> the door is NOT reliable yet. "
              "Calibrate the judge (plan_v2 G-cal) and run more sources/runs.")
    print("=" * 70)


if __name__ == "__main__":
    main()
