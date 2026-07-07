#!/usr/bin/env python3
"""
Dataset factory (M3) — turn the calibrated litmus pipeline into a hands-off
generator. For each (stimulus, archetype) it generates with the teacher, repairs
the distractors, then runs the 3-stage filter and KEEPS only survivors, looping
until it hits the per-slot target (or an attempt cap):

    generate (teacher)
      -> repair distractors (same model)
      -> Stage A  programmatic checks (checks.py; free)      fail => trash
      -> Stage B  judge near-miss / expert-quality           fail => trash
      -> Stage C  key-verifier (independent solve, k-of-n)   fail => trash
      -> keep

No per-item human grading. The per-stage yields it prints double as the G-yield
calibration (docs/plan_v2 M2.5): run it on a small target first, read the funnel,
then scale volume/budget from the measured keep rate.

Quick start:
    python eval/generate.py --split TRAIN --target 6 --repair            # real
    python eval/generate.py --split TRAIN --target 2 --limit 3 --dry-run # smoke
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import os
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
import verifier           # noqa: E402
from prompt_loader import LitmusPrompt, extract_items  # noqa: E402
from harness import load_sources, DEFAULT_ARCHETYPES, DIFFICULTY, dry_run_models  # noqa: E402


def _stage_a(item, source):
    prog = checks.run_checks(item, source)
    return (prog["disqualifying_ok"] and prog["wrong_era_le1"]), prog


class Funnel:
    """Thread-safe filter-funnel counters (also the G-yield report)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.c = {"generated": 0, "pass_a": 0, "pass_b": 0, "pass_c": 0, "kept": 0}

    def add(self, **kw):
        with self.lock:
            for k, v in kw.items():
                self.c[k] += v

    def report(self):
        c = self.c
        def rate(a, b):
            return f"{(a / b):.0%}" if b else "n/a"
        return (
            f"  generated : {c['generated']}\n"
            f"  Stage A (checks)   kept {c['pass_a']:4d}  ({rate(c['pass_a'], c['generated'])} of generated)\n"
            f"  Stage B (judge)    kept {c['pass_b']:4d}  ({rate(c['pass_b'], c['pass_a'])} of A)\n"
            f"  Stage C (verifier) kept {c['pass_c']:4d}  ({rate(c['pass_c'], c['pass_b'])} of B)\n"
            f"  KEPT (net)         {c['kept']:4d}  ({rate(c['kept'], c['generated'])} net keep)"
        )


def run_slot(source, archetype, *, gen_cfg, judge_cfg, ver_cfg, prompt, cfg, funnel, lock, out_records):
    """Generate-to-target for one (source, archetype). Returns kept records."""
    kept = []
    attempts = 0
    while len(kept) < cfg["target"] and attempts < cfg["cap"]:
        attempts += 1
        system, user = prompt.build(
            source=source["text"], attribution=source.get("attribution", ""), note="",
            n=cfg["n"], archetypes=archetype, difficulty=DIFFICULTY,
            include_fewshot=cfg["fewshot"])
        try:
            raw = providers.generate(gen_cfg, system, user, cfg["temperature"], role="teacher")
            items = extract_items(raw)
        except providers.ProviderError:
            items = []
        funnel.add(generated=len(items))
        for it in items:
            if len(kept) >= cfg["target"]:
                break
            it.setdefault("archetype", archetype)
            if cfg["repair"]:
                it = repair.repair_item(gen_cfg, source, it, cfg["temperature"], role="teacher")
            ok_a, prog = _stage_a(it, source)
            if not ok_a:
                continue
            funnel.add(pass_a=1)
            if cfg["dry_run"]:
                j = judge._mock_judgment("teacher") if hasattr(judge, "_mock_judgment") else None
                j = judge._normalize(j)
            else:
                j = judge.judge_item(judge_cfg, source, it, role="teacher")
            if not judge.near_grade(prog["disqualifying_ok"] and prog["wrong_era_le1"], j):
                continue
            funnel.add(pass_b=1)
            if cfg["dry_run"]:
                v = {"verified": True, "agreement": 1.0, "votes": {it.get("answer", "A"): 3}, "n_solved": 3}
            else:
                v = verifier.verify_item(ver_cfg, source, it, n=cfg["verify_n"])
            if not v["verified"]:
                continue
            funnel.add(pass_c=1, kept=1)
            kept.append({
                "source_id": source["id"], "archetype": it.get("archetype"),
                "stem": it.get("stem"), "options": it.get("options"),
                "answer": it.get("answer"), "answer_dating": it.get("answer_dating"),
                "rationale": it.get("rationale"), "trap_types": it.get("trap_types"),
                "period": source.get("period"), "themes": source.get("themes"),
                "judge": {k: j.get(k) for k in ("spec_adherence", "distractor_craft",
                                                "outside_knowledge_skill_fit",
                                                "distractors_period_plausible")},
                "verify": v, "repaired": bool(it.get("_repaired")),
                "provenance": {"generator": gen_cfg["name"], "judge": judge_cfg.get("name"),
                               "verifier": ver_cfg.get("name"), "attempts": attempts},
            })
    with lock:
        out_records.extend(kept)
    status = "OK " if len(kept) >= cfg["target"] else "SHORT"
    sys.stdout.write(f"  [{status}] {source['id']:28} {archetype:16} kept {len(kept)}/{cfg['target']} "
                     f"({attempts} attempt(s))\n")
    sys.stdout.flush()
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=os.path.join(HERE, "models.json"))
    ap.add_argument("--split", default="TRAIN", help="which split's sources to generate on")
    ap.add_argument("--target", type=int, default=6, help="kept items per (source, archetype)")
    ap.add_argument("--cap", type=int, default=4, help="max generation attempts per slot")
    ap.add_argument("--n", type=int, default=6, help="items requested per generation call")
    ap.add_argument("--verify-n", type=int, default=3, help="independent solves per item (key-verifier)")
    ap.add_argument("--repair", action="store_true", help="run the distractor-repair pass (recommended)")
    ap.add_argument("--fewshot", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--archetypes", default=DEFAULT_ARCHETYPES)
    ap.add_argument("--limit", type=int, default=0, help="limit number of sources (smoke test)")
    ap.add_argument("--concurrency", type=int, default=6, help="parallel (source,archetype) slots")
    ap.add_argument("--dry-run", action="store_true", help="mock generator/judge/verifier (no keys/network)")
    ap.add_argument("--out", default=None, help="output jsonl (default data/generated/<split>.jsonl)")
    args = ap.parse_args()

    if args.dry_run:
        models = dry_run_models()
        gen_cfg = models["teacher"]
        judge_cfg = models["judge"]
        ver_cfg = models["judge"]
    else:
        if not os.path.exists(args.models):
            raise SystemExit(f"model config not found: {args.models}")
        models = json.load(open(args.models))
        gen_cfg = models.get("generator") or models.get("teacher")
        judge_cfg = models.get("judge")
        ver_cfg = models.get("verifier") or judge_cfg
        if not gen_cfg or not judge_cfg:
            raise SystemExit("need a 'teacher'/'generator' and a 'judge' in the models file")
        if not models.get("verifier"):
            print("note: no 'verifier' configured — using the judge model as key-verifier "
                  "(prefer a 3rd family; add a 'verifier' entry to models.json).")

    sources = load_sources(args.split)
    if args.limit:
        sources = sources[:args.limit]
    if not sources:
        raise SystemExit(f"split {args.split!r} has no sources. Expand the corpus (A3) and "
                         "repopulate data/splits.json (TRAIN is empty by default).")
    archs = [a.strip() for a in args.archetypes.split(",") if a.strip()]

    prompt = LitmusPrompt.from_file(os.path.join(ROOT, "prompts", "litmus_generation_prompt.md"))
    cfg = {"target": args.target, "cap": args.cap, "n": args.n, "repair": args.repair,
           "fewshot": args.fewshot, "temperature": args.temperature, "verify_n": args.verify_n,
           "dry_run": args.dry_run}

    funnel = Funnel()
    out_records, lock = [], threading.Lock()
    slots = [(s, a) for s in sources for a in archs]
    print(f"generating {len(slots)} slots ({len(sources)} sources x {len(archs)} archetypes), "
          f"target {args.target}/slot, cap {args.cap}"
          + (" [DRY-RUN]" if args.dry_run else "") + (" +repair" if args.repair else ""))
    t0 = time.time()
    workers = 1 if (gen_cfg.get("provider") in ("ollama", "mock")) else args.concurrency
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_slot, s, a, gen_cfg=gen_cfg, judge_cfg=judge_cfg, ver_cfg=ver_cfg,
                          prompt=prompt, cfg=cfg, funnel=funnel, lock=lock, out_records=out_records)
                for s, a in slots]
        for f in cf.as_completed(futs):
            f.result()

    out_path = args.out or os.path.join(ROOT, "data", "generated", f"{args.split.lower()}.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "split": args.split, "archetypes": archs, "target_per_slot": args.target,
            "kept": len(out_records), "elapsed_s": round(time.time() - t0, 1),
            "dry_run": args.dry_run, "repair": args.repair}
    json.dump(meta, open(out_path.replace(".jsonl", "_meta.json"), "w"), indent=2)

    print("\n" + "=" * 60)
    print("FILTER FUNNEL (also your G-yield):")
    print(funnel.report())
    print(f"\nkept {len(out_records)} items -> {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
