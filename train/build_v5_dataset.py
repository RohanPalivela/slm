#!/usr/bin/env python3
"""Build the v5 semantic-preservation dataset from independently audited v4 anchors.

The corrected v4 evaluation showed that the adapter learned the product contract
while regressing on unique keys, single-best answers, and distractor quality.
V5 therefore removes legacy generated survivors and repeated source exposures.
It retains only independently audited, expert-grade, human-curated causal
anchors, with one target per source and archetype.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "train"))

import checks  # noqa: E402
from audit_dataset import audit_record, rebalance_answers  # noqa: E402
from source_utils import source_genre  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def current_rubric_expert_pass(row: dict) -> bool:
    judgment = row.get("judge") or {}
    review = row.get("review") or {}
    return bool(
        review.get("current_rubric_complete") is True
        and judgment.get("_status", "ok") == "ok"
        and judgment.get("requires_outside_knowledge") is True
        and judgment.get("every_distractor_named_trap") is True
        and judgment.get("distractors_period_plausible") is True
        and judgment.get("skill_matches_command_phrase") is True
        and judgment.get("key_historically_correct") is True
        and judgment.get("key_uniquely_best") is True
        and judgment.get("single_best_answer") is True
        and judgment.get("spec_adherence") == 2
        and judgment.get("distractor_craft") == 2
        and judgment.get("outside_knowledge_skill_fit") == 2
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audited-v4",
        default=str(ROOT / "data/generated/train_v4_audited_clean.jsonl"),
    )
    parser.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "data/generated/train_v5_clean.jsonl"))
    parser.add_argument(
        "--report",
        default=str(ROOT / "data/generated/train_v5_build_report.json"),
    )
    args = parser.parse_args()

    audited_path = Path(args.audited_v4)
    audited = load_jsonl(audited_path)
    sources_path = Path(args.sources)
    sources = {row["id"]: row for row in load_jsonl(sources_path)}

    expert_rows = [row for row in audited if current_rubric_expert_pass(row)]
    curated_rows = [
        row for row in expert_rows
        if row.get("quality_tier") == "curated_causal_anchor"
    ]

    seen_pairs: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for original in sorted(
        curated_rows,
        key=lambda row: (str(row.get("source_id")), str(row.get("archetype"))),
    ):
        pair = (str(original.get("source_id")), str(original.get("archetype")))
        if pair in seen_pairs:
            raise SystemExit(f"duplicate curated source/archetype pair: {pair}")
        seen_pairs.add(pair)
        row = dict(original)
        row["dataset_version"] = "v5"
        row["sft_repeats"] = 1
        row["v5_selection"] = {
            "policy": "independent_current_rubric_expert_curated_only_v1",
            "reason": (
                "Retained as an independently audited expert-grade curated causal anchor; "
                "legacy generated survivors and repeated source exposures are excluded."
            ),
        }
        rows.append(row)

    rebalance_answers(rows)

    failures = []
    for index, row in enumerate(rows, 1):
        source = sources.get(row.get("source_id"))
        if source is None:
            failures.append((index, row.get("source_id"), "missing_source"))
            continue
        deterministic = audit_record(row, source)
        programmatic = checks.run_checks(row, source, row.get("archetype"))
        if (
            deterministic
            or not programmatic.get("trap_rationales_align")
            or not programmatic.get("craft_ok")
            or not programmatic.get("disqualifying_ok")
            or not programmatic.get("homogeneous_length")
        ):
            failures.append(
                {
                    "index": index,
                    "source_id": row.get("source_id"),
                    "archetype": row.get("archetype"),
                    "deterministic": deterministic,
                    "programmatic": programmatic,
                }
            )
    if failures:
        print(json.dumps(failures[:10], indent=2, ensure_ascii=False))
        raise SystemExit(f"v5 build failed: {len(failures)} target(s) failed validation")

    source_ids = {row["source_id"] for row in rows}
    report = {
        "dataset_version": "v5",
        "selection_policy": "independent_current_rubric_expert_curated_only_v1",
        "input_audited_v4_sha256": hashlib.sha256(audited_path.read_bytes()).hexdigest(),
        "source_corpus_sha256": hashlib.sha256(sources_path.read_bytes()).hexdigest(),
        "input_audited_v4_records": len(audited),
        "input_current_rubric_expert_records": len(expert_rows),
        "excluded_legacy_or_generated_records": len(expert_rows) - len(curated_rows),
        "excluded_non_expert_records": len(audited) - len(expert_rows),
        "output_records": len(rows),
        "source_count": len(source_ids),
        "archetype_distribution": dict(Counter(row["archetype"] for row in rows)),
        "answer_distribution": dict(Counter(row["answer"] for row in rows)),
        "source_genres": dict(
            Counter(source_genre(sources[source_id]) for source_id in source_ids)
        ),
        "sft_repeats": dict(Counter(row["sft_repeats"] for row in rows)),
        "design_decisions": [
            "Use only records that passed every current-rubric expert gate.",
            "Use only manually curated causal anchors with independent audit provenance.",
            "Remove legacy model-generated survivors and repeated target exposure.",
            "Keep exactly one target per source and archetype.",
            "Use one SFT exposure per retained target.",
        ],
    }

    output_path = Path(args.out)
    dump_jsonl(output_path, rows)
    report["output_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"wrote v5 clean set -> {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
