#!/usr/bin/env python3
"""Deterministic readiness checks before retraining the APUSH QLoRA model."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import checks  # noqa: E402
from prompt_loader import extract_items  # noqa: E402
from source_utils import source_genre  # noqa: E402

OPTION_LABEL = re.compile(r"^\s*[A-D][).:]\s+")
REQUIRED_ITEM_FIELDS = {
    "archetype", "period", "theme", "stem", "options", "answer",
    "answer_dating", "rationale", "trap_types", "requires_outside_knowledge",
}
REQUIRED_CLEAN_FIELDS = (REQUIRED_ITEM_FIELDS - {"theme"}) | {"themes"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def fail(failures: list[str], message: str) -> None:
    failures.append(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default=str(ROOT / "data/generated/train_clean.jsonl"))
    ap.add_argument("--sft", default=str(ROOT / "data/generated/train_sft_clean.jsonl"))
    ap.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    ap.add_argument("--splits", default=str(ROOT / "data/splits.json"))
    ap.add_argument("--prompt", default=str(ROOT / "prompts/litmus_generation_prompt.md"))
    args = ap.parse_args()

    clean = load_jsonl(Path(args.clean))
    sft = load_jsonl(Path(args.sft))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))["splits"]
    prompt_text = Path(args.prompt).read_text(encoding="utf-8")
    failures: list[str] = []
    warnings: list[str] = []

    if len(clean) != len(sft):
        fail(failures, f"clean/SFT count mismatch: {len(clean)} vs {len(sft)}")
    if len(clean) < 700:
        fail(failures, f"clean set unexpectedly small: {len(clean)}")

    answers = Counter(row.get("answer") for row in clean)
    if set(answers) != set("ABCD") or max(answers.values()) - min(answers.values()) > 1:
        fail(failures, f"answer distribution not balanced: {dict(answers)}")

    arch = Counter(row.get("archetype") for row in clean)
    if set(arch) != {"CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE"}:
        fail(failures, f"unexpected archetypes: {dict(arch)}")
    if min(arch.values()) / max(arch.values()) < 0.9:
        fail(failures, f"archetype imbalance too large: {dict(arch)}")

    train_ids = set(splits["TRAIN"]["source_ids"])
    heldout_ids = set(splits["LITMUS"]["source_ids"]) | set(splits["EVAL_HELDOUT"]["source_ids"])
    clean_source_ids = {row.get("source_id") for row in clean}
    genre_counts = Counter(source_genre(sources.get(sid), sid or "") for sid in clean_source_ids)
    speech_share = genre_counts.get("speech_or_argument", 0) / max(len(clean_source_ids), 1)
    if speech_share > 0.60:
        warnings.append(
            f"source genre skew: {genre_counts.get('speech_or_argument', 0)}/{len(clean_source_ids)} "
            "training sources are speeches/arguments; add laws, court opinions, treaties, and executive actions"
        )
    overlap = clean_source_ids & heldout_ids
    if overlap:
        fail(failures, f"training clean set overlaps heldout/litmus sources: {sorted(overlap)[:10]}")
    missing_train = clean_source_ids - train_ids
    if missing_train:
        fail(failures, f"clean set contains source ids outside TRAIN: {sorted(missing_train)[:10]}")

    bad_schema = []
    date_fails = []
    verify_mismatch = []
    option_labels = []
    check_fails = Counter()
    synthesized_outside = 0
    correlated_verifier = 0
    for idx, row in enumerate(clean, 1):
        missing = REQUIRED_CLEAN_FIELDS - set(row)
        if missing:
            bad_schema.append((idx, "missing", sorted(missing)))
        if row.get("source_id") not in sources:
            bad_schema.append((idx, "missing_source", row.get("source_id")))
            continue
        prog = checks.run_checks(row, sources[row["source_id"]])
        for key in ("four_options", "one_key", "schema_ok", "craft_ok", "disqualifying_ok"):
            if not prog.get(key):
                check_fails[key] += 1
        if prog.get("date_direction") == "fail":
            date_fails.append((idx, row["source_id"], row["archetype"], row.get("answer_dating")))
        verify = row.get("verify") or {}
        if verify.get("key") and verify.get("key") != row.get("answer"):
            verify_mismatch.append((idx, row["source_id"], row.get("answer"), verify.get("key")))
        provenance = row.get("provenance") or {}
        if provenance.get("judge") and provenance.get("judge") == provenance.get("verifier"):
            correlated_verifier += 1
        answer = str(row.get("answer", "")).strip().upper()[:1]
        opts = row.get("options") or []
        if answer in "ABCD" and len(opts) == 4:
            legacy = f"{opts['ABCD'.index(answer)]} — {row.get('answer_dating', '')}".strip(" —")
            if str(row.get("requires_outside_knowledge", "")).strip() == legacy:
                synthesized_outside += 1
        for option in row.get("options") or []:
            if OPTION_LABEL.search(str(option)):
                option_labels.append((idx, option))

    if bad_schema:
        fail(failures, f"schema issues: {bad_schema[:5]}")
    if date_fails:
        fail(failures, f"date direction failures: {date_fails[:5]}")
    if verify_mismatch:
        fail(failures, f"verify key mismatches: {verify_mismatch[:5]}")
    if option_labels:
        fail(failures, f"embedded option labels: {option_labels[:5]}")
    if check_fails:
        fail(failures, f"programmatic check failures: {dict(check_fails)}")
    if synthesized_outside:
        warnings.append(
            f"{synthesized_outside}/{len(clean)} outside-knowledge explanations were mechanically "
            "backfilled from key+dating rather than preserved from generation"
        )
    if correlated_verifier:
        warnings.append(
            f"{correlated_verifier}/{len(clean)} records used the same model for judge and verifier"
        )

    if '"options": ["A ...", "B ...", "C ...", "D ..."]' in prompt_text:
        fail(failures, "prompt still asks for labeled option strings")

    bad_sft = []
    for idx, row in enumerate(sft, 1):
        messages = row.get("messages") or []
        if len(messages) != 3:
            bad_sft.append((idx, "bad_message_count"))
            continue
        items = extract_items(messages[-1].get("content", ""))
        if len(items) != 1:
            bad_sft.append((idx, "assistant_not_one_json_item"))
            continue
        item = items[0]
        if REQUIRED_ITEM_FIELDS - set(item):
            bad_sft.append((idx, "assistant_missing_fields", sorted(REQUIRED_ITEM_FIELDS - set(item))))
        if any(OPTION_LABEL.search(str(option)) for option in item.get("options") or []):
            bad_sft.append((idx, "assistant_option_labels"))
    if bad_sft:
        fail(failures, f"SFT issues: {bad_sft[:5]}")

    report = {
        "clean_records": len(clean),
        "sft_records": len(sft),
        "answer_distribution": dict(answers),
        "archetype_distribution": dict(arch),
        "source_count": len(clean_source_ids),
        "source_genres": dict(genre_counts),
        "warnings": warnings,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if failures:
        print("RETRAIN_READY: no")
        return 1
    print("RETRAIN_READY: yes_with_warnings" if warnings else "RETRAIN_READY: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
