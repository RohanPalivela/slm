#!/usr/bin/env python3
"""Retry unavailable eval judgments and preserve raw judge responses.

The input artifact is never modified. Only records with unavailable legacy or
current judgments are retried by default. Use --all to refresh every judgment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import checks  # noqa: E402
import judge  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def unavailable(judgment: dict | None) -> bool:
    if not judgment:
        return True
    if judgment.get("_status", "ok") != "ok":
        return True
    return "unparseable" in str(judgment.get("notes", "")).lower()


def sanitized_model_config(cfg: dict) -> dict:
    sensitive_parts = ("password", "secret", "api_key", "access_token")
    return {
        key: (
            "<redacted>"
            if any(part in key.lower() for part in sensitive_parts)
            and not key.lower().endswith("_env")
            else value
        )
        for key, value in cfg.items()
        if not key.startswith("_")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", required=True)
    parser.add_argument("--models", default=str(ROOT / "eval/models.json"))
    parser.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--meta-out", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    records = load_jsonl(Path(args.items))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    models = json.loads(Path(args.models).read_text(encoding="utf-8"))
    judge_cfg = models.get("judge")
    if not judge_cfg:
        raise SystemExit("models file has no judge configuration")

    updated = []
    status_counts: Counter[str] = Counter()
    for index, record in enumerate(records, 1):
        old_judgment = record.get("judge")
        if not args.all and not unavailable(old_judgment):
            updated.append(record)
            status_counts["preserved"] += 1
            continue
        source_id = record.get("source_id")
        source = sources.get(source_id)
        item = record.get("item") or {
            key: record.get(key)
            for key in (
                "archetype", "stem", "options", "answer", "answer_dating",
                "rationale", "trap_types", "requires_outside_knowledge",
            )
        }
        if source is None:
            raise SystemExit(f"record {index} references unknown source: {source_id}")
        programmatic = checks.run_checks(item, source)
        new_judgment = judge.judge_item(judge_cfg, source, item, role=record.get("role", ""))
        craft_ok = programmatic["disqualifying_ok"] and programmatic["craft_ok"]
        key_valid = (
            None
            if new_judgment.get("key_valid") is None
            else bool(new_judgment["key_valid"] and programmatic["disqualifying_ok"])
        )
        refreshed = {
            **record,
            "prog": programmatic,
            "judge": new_judgment,
            "near_miss": judge.near_grade(craft_ok, new_judgment),
            "expert_grade": judge.expert_grade(craft_ok, new_judgment),
            "key_valid": key_valid,
            "previous_judge": old_judgment,
        }
        updated.append(refreshed)
        status = new_judgment.get("_status", "ok")
        status_counts[f"rejudged_{status}"] += 1
        print(f"{index}/{len(records)} {record.get('model')} {source_id} {record.get('archetype')} -> {status}")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in updated:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    safe_config = sanitized_model_config(judge_cfg)
    meta = {
        "schema_version": "eval_rejudge_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": str(Path(args.items).resolve()),
        "input_sha256": hashlib.sha256(Path(args.items).read_bytes()).hexdigest(),
        "output": str(output.resolve()),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "sources_sha256": hashlib.sha256(Path(args.sources).read_bytes()).hexdigest(),
        "judge_code_sha256": hashlib.sha256((ROOT / "eval/judge.py").read_bytes()).hexdigest(),
        "judge_prompt_sha256": hashlib.sha256(
            (judge.JUDGE_SYSTEM + "\n" + judge.JUDGE_USER_TMPL).encode("utf-8")
        ).hexdigest(),
        "judge": {
            "name": judge_cfg.get("name"),
            "provider": judge_cfg.get("provider"),
            "model": judge_cfg.get("model"),
            "revision": judge_cfg.get("revision") or judge_cfg.get("model_revision"),
            "config": safe_config,
            "config_sha256": hashlib.sha256(
                json.dumps(safe_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "refresh_all": args.all,
        "records": len(updated),
        "status_counts": dict(status_counts),
    }
    meta_path = (
        Path(args.meta_out)
        if args.meta_out
        else output.with_name(output.stem + "_meta.json")
    )
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(status_counts), indent=2))
    print(f"wrote {len(updated)} records -> {output}")
    print(f"wrote rejudge metadata -> {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
