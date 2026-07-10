#!/usr/bin/env python3
"""Re-score a source-stratified sample of final SFT targets with the current rubric."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import checks  # noqa: E402
import judge  # noqa: E402
from source_utils import source_genre  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default=str(ROOT / "data/generated/train_clean.jsonl"))
    ap.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    ap.add_argument("--models", default=str(ROOT / "eval/models.json"))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "results/training_semantic_audit.jsonl"))
    args = ap.parse_args()

    rows = load_jsonl(Path(args.clean))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    models = json.loads(Path(args.models).read_text(encoding="utf-8"))
    judge_cfg = models.get("judge")
    if not judge_cfg:
        raise SystemExit("models file has no judge configuration")

    # Round-robin over genres so the dominant speech genre cannot consume the sample.
    by_genre: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_genre[source_genre(sources.get(row.get("source_id")), row.get("source_id", ""))].append(row)
    rng = random.Random(args.seed)
    for group in by_genre.values():
        rng.shuffle(group)
    sample: list[dict] = []
    while len(sample) < min(args.n, len(rows)) and any(by_genre.values()):
        for genre in sorted(by_genre):
            if by_genre[genre] and len(sample) < args.n:
                sample.append(by_genre[genre].pop())

    out = []
    for i, item in enumerate(sample, 1):
        source = sources[item["source_id"]]
        prog = checks.run_checks(item, source)
        verdict = judge.judge_item(judge_cfg, source, item, role="teacher")
        craft_ok = prog["disqualifying_ok"] and prog["craft_ok"]
        out.append({
            "source_id": item["source_id"],
            "source_genre": source_genre(source),
            "archetype": item.get("archetype"),
            "stem": item.get("stem"),
            "answer": item.get("answer"),
            "prog": prog,
            "judge": verdict,
            "near_miss": judge.near_grade(craft_ok, verdict),
            "expert_grade": judge.expert_grade(craft_ok, verdict),
            "key_valid": verdict["key_valid"] and prog["disqualifying_ok"],
        })
        print(f"{i}/{len(sample)} {item['source_id']} key={out[-1]['key_valid']} near={out[-1]['near_miss']}")

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("summary", {
        "n": len(out),
        "key_valid": sum(r["key_valid"] for r in out) / len(out) if out else None,
        "near_miss": sum(r["near_miss"] for r in out) / len(out) if out else None,
        "genres": dict(Counter(r["source_genre"] for r in out)),
    })
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
