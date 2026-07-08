#!/usr/bin/env python3
"""
Corpus integrity audit — catch stimuli whose TEXT doesn't match their ATTRIBUTION
(the failure mode when a Wikisource search resolves to the wrong page, e.g. a
"Reagan 1983" entry that actually fetched a modern State of the Union).

Two layers:
  offline (default, no key): duplicate/near-identical text across sources, and
      anachronisms (a year in the text later than the source year).
  --llm (needs the gateway judge): asks a model whether the excerpt plausibly
      comes from the claimed author/title/year — catches semantic mismatches the
      offline checks can't (wrong speaker, wrong topic, publisher blurbs).

Usage:
    python eval/audit_corpus.py                 # offline checks
    python eval/audit_corpus.py --llm           # + model-based attribution check
"""
from __future__ import annotations
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SEED = os.path.join(ROOT, "data", "seed_stimuli.jsonl")

AUDIT_SYSTEM = """You verify citation integrity. Given an ATTRIBUTION (author, title, \
year) and an EXCERPT, decide whether the excerpt plausibly comes from THAT source. \
Flag mismatches: wrong author/speaker, wrong era/topic, or a description ABOUT the \
work rather than the work itself. Return ONLY JSON: {"match": true|false, "reason": "<one sentence>"}."""


def _load_primary():
    rows = [json.loads(l) for l in open(SEED, encoding="utf-8") if l.strip()]
    return [r for r in rows if r.get("stimulus_type") == "primary_text"]


def offline_checks(prim):
    flags = []
    # duplicate / near-identical text (mis-fetch resolving two ids to one page)
    by_head = collections.defaultdict(list)
    for r in prim:
        by_head[r["text"][:80].lower()].append(r["id"])
    for ids in by_head.values():
        if len(ids) > 1:
            flags.append(("DUPLICATE_TEXT", ids))
    # anachronism: a year in the text later than the source year (+1 tolerance)
    for r in prim:
        yrs = [int(y) for y in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", r["text"])]
        future = sorted({y for y in yrs if y > r["year"] + 1})
        if future:
            flags.append(("ANACHRONISM", [r["id"], f"src {r['year']} mentions {future}"]))
    return flags


def llm_checks(prim, models_path):
    import providers
    from prompt_loader import extract_items
    cfg = json.load(open(models_path)).get("judge")
    if not cfg:
        raise SystemExit("no 'judge' model configured for --llm audit")
    bad = []
    for r in prim:
        user = (f"ATTRIBUTION: {r['attribution']} (author: {r.get('author','?')}, year: {r['year']})\n"
                f"EXCERPT:\n\"\"\"\n{r['text']}\n\"\"\"\n\nReturn ONLY the JSON verdict.")
        try:
            raw = providers.generate(cfg, AUDIT_SYSTEM, user, 0.0, role="judge")
            parsed = extract_items(raw)
            v = parsed[0] if parsed else {}
        except Exception as e:  # noqa: BLE001
            print(f"  ? {r['id']}: audit call failed ({e})")
            continue
        if not v.get("match", True):
            bad.append((r["id"], v.get("reason", "")))
        print(f"  {'OK ' if v.get('match', True) else 'BAD'}  {r['id']:34} {v.get('reason','')[:70]}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", action="store_true", help="also run the model-based attribution check")
    ap.add_argument("--models", default=os.path.join(HERE, "models.json"))
    args = ap.parse_args()

    prim = _load_primary()
    print(f"auditing {len(prim)} primary sources\n")
    flags = offline_checks(prim)
    print("=== offline checks ===")
    if not flags:
        print("  clean (no duplicate text, no anachronisms)")
    for kind, detail in flags:
        print(f"  [{kind}] {detail}")

    if args.llm:
        print("\n=== LLM attribution check ===")
        bad = llm_checks(prim, args.models)
        print(f"\n{len(bad)} attribution mismatch(es) flagged" + (":" if bad else ""))
        for i, reason in bad:
            print(f"  - {i}: {reason}")
    else:
        print("\n(run with --llm for the model-based attribution check)")


if __name__ == "__main__":
    main()
