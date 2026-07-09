#!/usr/bin/env python3
"""
Pretty-print results/litmus_items.jsonl for error analysis: for each generated
item, show the stem/answer, PASS/FAIL, which programmatic checks tripped, and the
judge's per-dimension scores + notes (so you can see WHY an item failed and
whether the judge is being reasonable).

Usage:
    python eval/show_items.py                      # all items
    python eval/show_items.py --model claude-opus-4-8
    python eval/show_items.py --fails-only
    python eval/show_items.py --path results/litmus_items.jsonl
"""
from __future__ import annotations
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.path.join(ROOT, "results", "litmus_items.jsonl"))
    ap.add_argument("--model", default=None, help="filter by model name substring")
    ap.add_argument("--fails-only", action="store_true", help="only items that are not expert-grade")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        raise SystemExit(f"not found: {args.path} (run the harness first)")

    recs = [json.loads(l) for l in open(args.path, encoding="utf-8") if l.strip()]
    if args.model:
        recs = [r for r in recs if args.model.lower() in r["model"].lower()]
    if args.fails_only:
        recs = [r for r in recs if not r["expert_grade"]]

    for r in recs:
        eg = "PASS" if r["expert_grade"] else "FAIL"
        kv = r.get("key_valid")
        print("=" * 78)
        print(f"[{eg}] {r['model']} ({r['role']}) | {r['source_id']} | {r['archetype']} "
              f"| key_valid={kv}")
        print(f"  stem: {r.get('stem')}")
        opts = r.get("options") or []
        ans = str(r.get("answer", "")).strip().upper()[:1]
        for i, o in enumerate(opts):
            mark = " <== keyed" if "ABCD"[i:i + 1] == ans else ""
            print(f"    {'ABCD'[i] if i < 4 else '?'}) {o}{mark}")
        # programmatic checks that tripped
        prog = r.get("prog") or {}
        trips = []
        if prog.get("four_options") is False: trips.append("not 4 options")
        if prog.get("one_key") is False: trips.append("no single key")
        if prog.get("no_all_none_absolute") is False: trips.append("all/none/absolute word")
        if prog.get("source_leak"): trips.append("source-leak (echoes source)")
        if prog.get("date_direction") == "fail": trips.append("anachronism (date direction)")
        if prog.get("trap_diversity_ge2") is False: trips.append("<2 distinct traps")
        if prog.get("trap_count_3") is False: trips.append("trap_types length != 3")
        if prog.get("trap_types_valid") is False: trips.append("invalid trap id")
        if prog.get("no_parenthetical_option_dates") is False: trips.append("parenthetical option date")
        if prog.get("rationale_complete") is False: trips.append("incomplete rationale")
        if prog.get("rationale_marks_key") is False: trips.append("key rationale mismatch")
        if prog.get("homogeneous_length") is False: trips.append("option length imbalance")
        print(f"  programmatic: {'OK' if prog.get('disqualifying_ok') else 'FAIL'}"
              + (f"  [{', '.join(trips)}]" if trips else ""))
        if "craft_ok" in prog:
            print(f"  craft/schema: {'OK' if prog.get('craft_ok') else 'FAIL'}")
        j = r.get("judge")
        if j:
            print(f"  judge dims: spec={j['spec_adherence']} distractor={j['distractor_craft']} "
                  f"outside/skill={j['outside_knowledge_skill_fit']}")
            jb = [k for k in ("requires_outside_knowledge", "every_distractor_named_trap",
                              "distractors_period_plausible", "skill_matches_command_phrase",
                              "single_best_answer", "key_historically_correct", "key_uniquely_best")
                  if not j.get(k)]
            if jb:
                print(f"  judge flagged FALSE: {', '.join(jb)}")
            print(f"  judge notes: {j.get('notes')}")
        else:
            print("  judge: (not run)")
    print("=" * 78)
    print(f"{len(recs)} items shown"
          + (f" (model~{args.model})" if args.model else "")
          + (" (fails only)" if args.fails_only else ""))


if __name__ == "__main__":
    main()
