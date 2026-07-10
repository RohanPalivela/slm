#!/usr/bin/env python3
"""Apply a complete independent semantic audit to the provisional v4 set."""
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
from build_v4_dataset import assign_balanced_sft_repeats  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def review_id(row: dict) -> str:
    return hashlib.sha256(
        f"{row.get('source_id')}\n{row.get('archetype')}\n{row.get('stem')}".encode("utf-8")
    ).hexdigest()


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", default=str(ROOT / "data/generated/train_v4_clean.jsonl"))
    parser.add_argument("--audit", default=str(ROOT / "results/training_semantic_audit.jsonl"))
    parser.add_argument(
        "--audit-meta",
        default=str(ROOT / "results/training_semantic_audit_meta.json"),
    )
    parser.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "data/generated/train_v4_audited_clean.jsonl"))
    parser.add_argument("--quarantine", default=str(ROOT / "data/generated/train_v4_semantic_quarantine.jsonl"))
    args = parser.parse_args()

    rows = load_jsonl(Path(args.clean))
    audit_rows = load_jsonl(Path(args.audit))
    audit_meta_path = Path(args.audit_meta)
    if not audit_meta_path.exists():
        raise SystemExit(f"semantic audit metadata not found: {audit_meta_path}")
    audit_meta = json.loads(audit_meta_path.read_text(encoding="utf-8"))
    clean_sha256 = hashlib.sha256(Path(args.clean).read_bytes()).hexdigest()
    audit_sha256 = hashlib.sha256(Path(args.audit).read_bytes()).hexdigest()
    if audit_meta.get("input_sha256") != clean_sha256:
        raise SystemExit("semantic audit metadata does not match the clean dataset hash")
    if audit_meta.get("audit_output_sha256") != audit_sha256:
        raise SystemExit("semantic audit JSONL hash does not match its metadata sidecar")
    if not audit_meta.get("independent_provenance"):
        raise SystemExit("semantic audit metadata does not certify an independent auditor family")
    if not audit_meta.get("full_dataset_audit"):
        raise SystemExit("semantic audit metadata says this was not a full-dataset audit")
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    audit_by_id = {}
    for audit in audit_rows:
        audit_id = audit.get("review_id")
        if not audit_id or audit_id in audit_by_id:
            raise SystemExit(f"missing or duplicate review_id in semantic audit: {audit_id}")
        audit_by_id[audit_id] = audit

    expected_ids = {review_id(row) for row in rows}
    if set(audit_meta.get("review_ids") or []) != expected_ids:
        raise SystemExit("semantic audit metadata review ids do not exactly cover the clean dataset")
    missing = expected_ids - set(audit_by_id)
    extra = set(audit_by_id) - expected_ids
    if missing or extra:
        raise SystemExit(
            f"semantic audit does not exactly cover v4: missing={len(missing)} extra={len(extra)}"
        )

    kept = []
    quarantine = []
    for row in rows:
        audit = audit_by_id[review_id(row)]
        verdict = audit.get("judge") or {}
        passes = bool(
            verdict.get("_status", "ok") == "ok"
            and audit.get("key_valid") is True
            and audit.get("near_miss") is True
        )
        if not passes:
            quarantine.append({
                "review_id": review_id(row),
                "source_id": row.get("source_id"),
                "archetype": row.get("archetype"),
                "reasons": {
                    "judge_status": verdict.get("_status", "unknown"),
                    "key_valid": audit.get("key_valid"),
                    "near_miss": audit.get("near_miss"),
                    "notes": verdict.get("notes"),
                },
                "record": row,
                "audit": audit,
            })
            continue
        updated = dict(row)
        updated["legacy_judge"] = row.get("judge")
        updated["judge"] = verdict
        updated["review"] = {
            "status": "independent_current_rubric_pass",
            "current_rubric_complete": True,
            "auditor": audit.get("auditor"),
            "auditor_config_sha256": (audit_meta.get("auditor") or {}).get("config_sha256"),
            "audit_timestamp": audit_meta.get("timestamp"),
            "audit_input_sha256": clean_sha256,
            "review_id": review_id(row),
        }
        kept.append(updated)

    rebalance_answers(kept)
    assign_balanced_sft_repeats(kept)
    failures = []
    for index, row in enumerate(kept, 1):
        source = sources[row["source_id"]]
        reasons = audit_record(row, source)
        programmatic = checks.run_checks(row, source)
        if (
            reasons
            or not programmatic.get("craft_ok")
            or not programmatic.get("disqualifying_ok")
            or not programmatic.get("homogeneous_length")
        ):
            failures.append((index, row["source_id"], row["archetype"], reasons, programmatic))
    if failures:
        raise SystemExit(f"post-audit records failed deterministic checks: {failures[:3]}")

    dump_jsonl(Path(args.out), kept)
    dump_jsonl(Path(args.quarantine), quarantine)
    report = {
        "input_records": len(rows),
        "kept_records": len(kept),
        "quarantined_records": len(quarantine),
        "archetypes": dict(Counter(row["archetype"] for row in kept)),
        "answers": dict(Counter(row["answer"] for row in kept)),
    }
    print(json.dumps(report, indent=2))
    print(f"wrote audited set -> {args.out}")
    print(f"wrote semantic quarantine -> {args.quarantine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
