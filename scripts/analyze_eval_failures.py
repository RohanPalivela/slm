#!/usr/bin/env python3
"""
Summarize notebook/harness eval outputs and bucket failure modes.

Inputs are the standalone notebook outputs:
  - items.jsonl: one parsed item per line
  - generation_attempts.json: one generation call per entry (optional)

The script does not call any model. It reuses saved judge/programmatic fields to
explain why a tuned run is losing key_valid / near_miss.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def pct(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{num / den:.0%}"


def fmt_rate(value) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def bucket_record(rec: dict) -> list[str]:
    buckets: list[str] = []
    prog = rec.get("prog") or {}
    judge = rec.get("judge") or {}
    item = rec.get("item") or {}

    if rec.get("key_valid") is False:
        if judge.get("key_historically_correct") is False:
            buckets.append("key_factually_wrong")
        if judge.get("key_uniquely_best") is False:
            buckets.append("key_not_unique")
        if not buckets:
            buckets.append("key_invalid_unspecified")

    if rec.get("near_miss") is False:
        if judge.get("requires_outside_knowledge") is False:
            buckets.append("source_paraphrase_or_no_outside_knowledge")
        if judge.get("skill_matches_command_phrase") is False:
            buckets.append("skill_mismatch")
        if judge.get("single_best_answer") is False:
            buckets.append("not_single_best")
        if judge.get("every_distractor_named_trap") is False:
            buckets.append("distractor_trap_invalid")
        if judge.get("distractors_period_plausible") is False:
            buckets.append("distractor_period_implausible")
        if min(
            int(judge.get("spec_adherence", 0) or 0),
            int(judge.get("distractor_craft", 0) or 0),
            int(judge.get("outside_knowledge_skill_fit", 0) or 0),
        ) < 1:
            buckets.append("judge_dimension_zero")

    if not prog.get("schema_ok", True):
        buckets.append("schema_invalid")
    if not prog.get("craft_ok", True):
        buckets.append("programmatic_craft_fail")
    if prog.get("date_direction") == "fail":
        buckets.append("date_direction_fail")
    if prog.get("source_leak"):
        buckets.append("source_leak")
    model_arch = item.get("_model_archetype") or rec.get("model_archetype")
    requested_arch = item.get("_requested_archetype") or rec.get("requested_archetype")
    if model_arch and requested_arch:
        if model_arch != requested_arch:
            buckets.append("archetype_label_mismatch")

    return buckets or ["passed_or_unjudged"]


def summarize(items: list[dict], attempts: list[dict]) -> dict:
    by_model: dict[str, list[dict]] = defaultdict(list)
    by_attempt_model: dict[str, list[dict]] = defaultdict(list)
    for rec in items:
        by_model[rec.get("model", "?")].append(rec)
    for att in attempts:
        by_attempt_model[att.get("model", "?")].append(att)
    for model in by_model:
        by_attempt_model.setdefault(model, [])
    for model in by_attempt_model:
        by_model.setdefault(model, [])

    summary = {}
    for model in sorted(by_model):
        recs = by_model[model]
        atts = by_attempt_model[model]
        n = len(recs)
        bucket_counts = Counter()
        arch_counts = defaultdict(Counter)
        examples = defaultdict(list)
        for rec in recs:
            buckets = bucket_record(rec)
            arch = rec.get("archetype") or (rec.get("item") or {}).get("archetype") or "?"
            for bucket in buckets:
                bucket_counts[bucket] += 1
                arch_counts[arch][bucket] += 1
                if bucket != "passed_or_unjudged" and len(examples[bucket]) < 5:
                    item = rec.get("item") or {}
                    examples[bucket].append({
                        "source_id": rec.get("source_id"),
                        "archetype": arch,
                        "answer": item.get("answer") or rec.get("answer"),
                        "stem": item.get("stem") or rec.get("stem"),
                        "judge_notes": (rec.get("judge") or {}).get("notes"),
                    })

        zero = sum(1 for a in atts if a.get("n_items") == 0)
        summary[model] = {
            "calls": len(atts),
            "zero_item_calls": zero,
            "parse_empty_rate": None if not atts else zero / len(atts),
            "parsed_items": n,
            "expert_grade": None if n == 0 else sum(1 for r in recs if r.get("expert_grade")) / n,
            "near_miss": None if n == 0 else sum(1 for r in recs if r.get("near_miss")) / n,
            "key_valid": None if n == 0 else sum(1 for r in recs if r.get("key_valid")) / n,
            "bucket_counts": dict(bucket_counts),
            "by_archetype": {arch: dict(counts) for arch, counts in arch_counts.items()},
            "examples": examples,
        }
    return summary


def print_report(summary: dict) -> None:
    print("| Model | Calls | Zero calls | Parsed | Expert | Near | Key valid | Top failures |")
    print("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |")
    for model, s in summary.items():
        n = s["parsed_items"]
        top = Counter(s["bucket_counts"])
        top.pop("passed_or_unjudged", None)
        top_text = ", ".join(f"{k}={v}" for k, v in top.most_common(4)) or "none"
        print(
            f"| {model} | {s['calls']} | {s['zero_item_calls']} | {n} | "
            f"{fmt_rate(s['expert_grade'])} | "
            f"{fmt_rate(s['near_miss'])} | "
            f"{fmt_rate(s['key_valid'])} | "
            f"{top_text} |"
        )
    print()
    for model, s in summary.items():
        print(f"## {model}")
        for bucket, count in Counter(s["bucket_counts"]).most_common():
            if bucket == "passed_or_unjudged":
                continue
            print(f"- {bucket}: {count}")
            for ex in s["examples"].get(bucket, [])[:3]:
                print(f"  - {ex['source_id']} {ex['archetype']}: {ex['stem']} [{ex.get('judge_notes')}]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="Path to notebook results/items.jsonl")
    ap.add_argument("--attempts", default=None, help="Path to notebook results/generation_attempts.json")
    ap.add_argument("--out", default=None, help="Optional JSON summary output")
    args = ap.parse_args()

    items = load_jsonl(Path(args.items))
    attempts = []
    if args.attempts and Path(args.attempts).exists():
        attempts = json.loads(Path(args.attempts).read_text(encoding="utf-8"))
    summary = summarize(items, attempts)
    print_report(summary)
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
