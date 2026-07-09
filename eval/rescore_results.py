#!/usr/bin/env python3
"""
Re-score an existing litmus_items.jsonl with the current deterministic checks.

This does NOT call any model. It is useful after tightening checks.py or the
aggregation logic: the saved item text and saved judge JSON are reused, then
near_miss/expert_grade/key_valid are recomputed with the latest gates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import checks          # noqa: E402
import judge           # noqa: E402
from harness import aggregate, load_sources, write_report  # noqa: E402
from prompt_loader import canonicalize_item_archetype  # noqa: E402


ITEM_FIELDS = (
    "archetype", "stem", "options", "answer", "answer_dating", "rationale",
    "trap_types",
)


def _load_meta(path: str | None, split: str) -> dict:
    if path and os.path.exists(path):
        meta = json.load(open(path, encoding="utf-8")).get("meta", {})
    else:
        meta = {}
    meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    meta.setdefault("split", split)
    meta.setdefault("n", 0)
    meta.setdefault("runs", 1)
    meta.setdefault("n_sources", 0)
    meta.setdefault("archetypes", "CAUSE_OF_SOURCE, EFFECT_OF_SOURCE")
    meta.setdefault("dry_run", False)
    meta.setdefault("no_judge", False)
    meta.setdefault("fewshot", False)
    meta.setdefault("repair", False)
    meta["rescored_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return meta


def _item_from_record(rec: dict) -> dict:
    item = {k: rec.get(k) for k in ITEM_FIELDS}
    return canonicalize_item_archetype(item, requested_archetype=rec.get("requested_archetype"))


def _rescore_record(rec: dict, source: dict) -> dict:
    item = _item_from_record(rec)
    prog = checks.run_checks(item, source)
    j = rec.get("judge")
    if j is None:
        expert_grade = near_miss = key_valid = None
    else:
        prog_ok = prog["disqualifying_ok"] and prog["craft_ok"]
        expert_grade = judge.expert_grade(prog_ok, j)
        near_miss = judge.near_grade(prog_ok, j)
        key_valid = bool(j.get("key_valid") and prog["disqualifying_ok"])
    return {**rec, "archetype": item.get("archetype"),
            "model_archetype": rec.get("model_archetype") or item.get("_model_archetype"),
            "requested_archetype": rec.get("requested_archetype") or item.get("_requested_archetype"),
            "item": item, "prog": prog, "expert_grade": expert_grade,
            "near_miss": near_miss, "key_valid": key_valid}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items", default=os.path.join(ROOT, "results", "litmus_items.jsonl"))
    ap.add_argument("--meta", default=os.path.join(ROOT, "results", "litmus_results.json"))
    ap.add_argument("--split", default=None, help="override split name; defaults to meta.split or EVAL_HELDOUT")
    ap.add_argument("--model", default=None, help="optional model name substring filter")
    ap.add_argument("--out", required=True, help="output directory for rescored report/items")
    args = ap.parse_args()

    if not os.path.exists(args.items):
        raise SystemExit(f"items file not found: {args.items}")
    meta_obj = json.load(open(args.meta, encoding="utf-8")) if os.path.exists(args.meta) else {"meta": {}}
    split = args.split or meta_obj.get("meta", {}).get("split") or "EVAL_HELDOUT"
    sources = {s["id"]: s for s in load_sources(split)}

    recs = [json.loads(l) for l in open(args.items, encoding="utf-8") if l.strip()]
    if args.model:
        recs = [r for r in recs if args.model.lower() in r.get("model", "").lower()]
    rescored = []
    missing = []
    for rec in recs:
        sid = rec.get("source_id")
        if sid not in sources:
            missing.append(sid)
            continue
        rescored.append(_rescore_record(rec, sources[sid]))
    if missing:
        raise SystemExit(f"items reference source ids not present in split {split}: {sorted(set(missing))}")

    results = {}
    for name in sorted({r["model"] for r in rescored}):
        model_scored = [r for r in rescored if r["model"] == name]
        role = model_scored[0].get("role", "candidate") if model_scored else "candidate"
        results[name] = {"role": role, "agg": aggregate(model_scored)}

    os.makedirs(args.out, exist_ok=True)
    meta = _load_meta(args.meta, split)
    if args.model:
        meta["model_filter"] = args.model
    write_report(results, meta, args.out)
    with open(os.path.join(args.out, "litmus_items.jsonl"), "w", encoding="utf-8") as f:
        for rec in rescored:
            out_rec = {k: v for k, v in rec.items() if k != "item"}
            f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
    print(f"rescored {len(rescored)} item(s) -> {args.out}")


if __name__ == "__main__":
    main()
