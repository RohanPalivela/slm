#!/usr/bin/env python3
"""
Format the generated dataset (data/generated/train.jsonl) into supervised
fine-tuning examples for QLoRA — one example per kept item.

Each example is a chat triple:
  system  = the litmus generation SYSTEM prompt (the full item-writing spec)
  user    = the litmus USER prompt for THAT source + archetype, asking for 1 item
  assistant = the item, as the JSON array the prompt asks for

Training masks everything but the assistant turn (loss on the JSON only), so the
model learns to emit exactly the schema given a source + archetype — the same
prompt shape the harness/inference uses.

Usage:
    python train/format_dataset.py
    python train/format_dataset.py --in data/generated/train.jsonl --out data/generated/train_sft.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from prompt_loader import LitmusPrompt  # noqa: E402

DIFFICULTY = "operational / test-day"
# The exact fields the generation prompt's OUTPUT FORMAT asks for (docs/prompt).
_ITEM_FIELDS = ("archetype", "period", "theme", "stem", "options", "answer",
                "answer_dating", "rationale", "trap_types")


def _completion_item(rec: dict) -> dict:
    """Rebuild a clean schema item from a kept training record (drop harness
    metadata like judge/verify/provenance)."""
    themes = rec.get("themes") or []
    item = {
        "archetype": rec.get("archetype"),
        "period": rec.get("period"),
        "theme": themes[0] if themes else None,
        "stem": rec.get("stem"),
        "options": rec.get("options"),
        "answer": rec.get("answer"),
        "answer_dating": rec.get("answer_dating"),
        "rationale": rec.get("rationale"),
        "trap_types": rec.get("trap_types"),
    }
    return {k: v for k, v in item.items() if v is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(ROOT, "data", "generated", "train.jsonl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "generated", "train_sft.jsonl"))
    ap.add_argument("--sources", default=os.path.join(ROOT, "data", "seed_stimuli.jsonl"))
    ap.add_argument("--fewshot", action="store_true", help="include the few-shot block in the system prompt")
    args = ap.parse_args()

    prompt = LitmusPrompt.from_file(os.path.join(ROOT, "prompts", "litmus_generation_prompt.md"))
    sources = {json.loads(l)["id"]: json.loads(l)
               for l in open(args.sources, encoding="utf-8") if l.strip()}
    recs = [json.loads(l) for l in open(args.inp, encoding="utf-8") if l.strip()]

    n_written, n_skipped = 0, 0
    with open(args.out, "w", encoding="utf-8") as f:
        for rec in recs:
            src = sources.get(rec["source_id"])
            if not src:
                n_skipped += 1
                continue
            system, user = prompt.build(
                source=src["text"], attribution=src.get("attribution", ""), note="",
                n=1, archetypes=rec.get("archetype", ""), difficulty=DIFFICULTY,
                include_fewshot=args.fewshot)
            completion = json.dumps([_completion_item(rec)], ensure_ascii=False)
            f.write(json.dumps({
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": completion},
                ],
                "source_id": rec["source_id"], "archetype": rec.get("archetype"),
            }, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"wrote {n_written} SFT examples -> {os.path.relpath(args.out, ROOT)}"
          + (f"  ({n_skipped} skipped: source not found)" if n_skipped else ""))
    print("Each example: system+user prompt (masked) -> assistant JSON (trained). "
          "Loss-on-response is applied by the trainer.")


if __name__ == "__main__":
    main()
