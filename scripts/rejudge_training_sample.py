#!/usr/bin/env python3
"""Re-score a source-stratified sample of final SFT targets with the current rubric."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import checks  # noqa: E402
import judge  # noqa: E402
from source_utils import source_genre  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_config_value(value, key: str = ""):
    sensitive_parts = ("password", "secret", "api_key", "access_token")
    lowered = key.lower()
    if any(part in lowered for part in sensitive_parts) and not lowered.endswith("_env"):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            child_key: sanitize_config_value(child_value, child_key)
            for child_key, child_value in value.items()
            if not child_key.startswith("_")
        }
    if isinstance(value, list):
        return [sanitize_config_value(child) for child in value]
    return value


def sanitized_model_config(cfg: dict) -> dict:
    return sanitize_config_value(cfg)


def identity_labels(cfg: dict) -> set[str]:
    labels = set()
    for key in ("name", "model"):
        value = str(cfg.get(key) or "").strip().lower()
        if value:
            labels.add(value)
            labels.add(value.rsplit("/", 1)[-1])
    return labels


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default=str(ROOT / "data/generated/train_v4_clean.jsonl"))
    ap.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    ap.add_argument("--models", default=str(ROOT / "eval/models.json"))
    ap.add_argument("--n", type=int, default=0, help="records to audit; 0 audits the full v4 set")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "results/training_semantic_audit.jsonl"))
    ap.add_argument(
        "--meta-out",
        default=str(ROOT / "results/training_semantic_audit_meta.json"),
    )
    ap.add_argument(
        "--allow-correlated-auditor",
        action="store_true",
        help="unsafe diagnostic override for an auditor that repeats legacy provenance",
    )
    args = ap.parse_args()

    rows = load_jsonl(Path(args.clean))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    models = json.loads(Path(args.models).read_text(encoding="utf-8"))
    judge_cfg = models.get("training_auditor") or models.get("verifier") or models.get("judge")
    if not judge_cfg:
        raise SystemExit("models file has no training_auditor or judge configuration")
    independent_slot = bool(models.get("training_auditor") or models.get("verifier"))
    legacy_identities = {
        str(value).strip().lower()
        for row in rows
        for value in (row.get("provenance") or {}).values()
        if isinstance(value, str) and value.strip()
    }
    auditor_labels = identity_labels(judge_cfg)
    auditor_overlap = {
        legacy
        for legacy in legacy_identities
        if any(
            auditor == legacy
            or (len(legacy) >= 6 and legacy in auditor)
            or (len(auditor) >= 6 and auditor in legacy)
            for auditor in auditor_labels
        )
    }
    if (not independent_slot or auditor_overlap) and not args.allow_correlated_auditor:
        detail = (
            f"overlap={sorted(auditor_overlap)}"
            if auditor_overlap
            else "no models.training_auditor or models.verifier is configured"
        )
        raise SystemExit(
            "the semantic audit requires an auditor family independent of legacy generator, "
            f"judge, and verifier provenance; {detail}. Use --allow-correlated-auditor only "
            "for a non-production diagnostic."
        )
    if not independent_slot or auditor_overlap:
        print("WARNING: correlated auditor explicitly allowed; this audit does not clear provenance warnings.")

    # Round-robin over genres so the dominant speech genre cannot consume the sample.
    by_genre: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_genre[source_genre(sources.get(row.get("source_id")), row.get("source_id", ""))].append(row)
    rng = random.Random(args.seed)
    for group in by_genre.values():
        rng.shuffle(group)
    target = len(rows) if args.n <= 0 else min(args.n, len(rows))
    sample: list[dict] = []
    while len(sample) < target and any(by_genre.values()):
        for genre in sorted(by_genre):
            if by_genre[genre] and len(sample) < target:
                sample.append(by_genre[genre].pop())

    out = []
    for i, item in enumerate(sample, 1):
        source = sources[item["source_id"]]
        prog = checks.run_checks(item, source)
        verdict = judge.judge_item(judge_cfg, source, item, role="teacher")
        craft_ok = prog["disqualifying_ok"] and prog["craft_ok"]
        judgment_ok = verdict.get("_status", "ok") == "ok" and verdict.get("key_valid") is not None
        review_id = hashlib.sha256(
            f"{item['source_id']}\n{item.get('archetype')}\n{item.get('stem')}".encode("utf-8")
        ).hexdigest()
        out.append({
            "review_id": review_id,
            "auditor": {
                "name": judge_cfg.get("name"),
                "provider": judge_cfg.get("provider"),
                "model": judge_cfg.get("model"),
            },
            "source_id": item["source_id"],
            "source_genre": source_genre(source),
            "archetype": item.get("archetype"),
            "stem": item.get("stem"),
            "answer": item.get("answer"),
            "prog": prog,
            "judge": verdict,
            "near_miss": judge.near_grade(craft_ok, verdict),
            "expert_grade": judge.expert_grade(craft_ok, verdict),
            "key_valid": bool(verdict["key_valid"] and prog["disqualifying_ok"]) if judgment_ok else None,
        })
        print(f"{i}/{len(sample)} {item['source_id']} status={verdict.get('_status', 'ok')} key={out[-1]['key_valid']} near={out[-1]['near_miss']}")

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    safe_config = sanitized_model_config(judge_cfg)
    meta = {
        "schema_version": "training_semantic_audit_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": str(Path(args.clean).resolve()),
        "input_sha256": hashlib.sha256(Path(args.clean).read_bytes()).hexdigest(),
        "audit_output": str(path.resolve()),
        "audit_output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sources_sha256": hashlib.sha256(Path(args.sources).read_bytes()).hexdigest(),
        "judge_code_sha256": hashlib.sha256((ROOT / "eval/judge.py").read_bytes()).hexdigest(),
        "judge_prompt_sha256": hashlib.sha256(
            (judge.JUDGE_SYSTEM + "\n" + judge.JUDGE_USER_TMPL).encode("utf-8")
        ).hexdigest(),
        "auditor": {
            "name": judge_cfg.get("name"),
            "provider": judge_cfg.get("provider"),
            "model": judge_cfg.get("model"),
            "revision": judge_cfg.get("revision") or judge_cfg.get("model_revision"),
            "config": safe_config,
            "config_sha256": sha256_json(safe_config),
        },
        "independent_provenance": bool(independent_slot and not auditor_overlap),
        "seed": args.seed,
        "requested_records": target,
        "audited_records": len(out),
        "full_dataset_audit": len(out) == len(rows),
        "review_ids": [row["review_id"] for row in out],
    }
    meta_path = Path(args.meta_out)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("summary", {
        "n": len(out),
        "judged": sum(r["near_miss"] is not None for r in out),
        "key_valid": (sum(bool(r["key_valid"]) for r in out if r["key_valid"] is not None) /
                      sum(r["key_valid"] is not None for r in out)) if any(r["key_valid"] is not None for r in out) else None,
        "near_miss": (sum(bool(r["near_miss"]) for r in out if r["near_miss"] is not None) /
                      sum(r["near_miss"] is not None for r in out)) if any(r["near_miss"] is not None for r in out) else None,
        "genres": dict(Counter(r["source_genre"] for r in out)),
    })
    print("wrote", path)
    print("wrote", meta_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
