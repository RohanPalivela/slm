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
LOOSE_OPTION_LABEL = re.compile(r"^\s*([A-D])(?:[).:]\s+|\s+(?=[A-Z]))")
REQUIRED_ITEM_FIELDS = {
    "archetype", "period", "theme", "stem", "options", "answer",
    "answer_dating", "rationale", "trap_types", "requires_outside_knowledge",
}
REQUIRED_CLEAN_FIELDS = (REQUIRED_ITEM_FIELDS - {"theme"}) | {"themes"}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def fail(failures: list[str], message: str) -> None:
    failures.append(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default=str(ROOT / "data/generated/train_v5_clean.jsonl"))
    ap.add_argument("--sft", default=str(ROOT / "data/generated/train_sft_v5.jsonl"))
    ap.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    ap.add_argument("--splits", default=str(ROOT / "data/splits.json"))
    ap.add_argument("--prompt", default=str(ROOT / "prompts/litmus_generation_prompt.md"))
    ap.add_argument("--min-records", type=int, default=64)
    ap.add_argument("--min-sources", type=int, default=32)
    ap.add_argument("--min-curated-anchors", type=int, default=64)
    args = ap.parse_args()

    clean = load_jsonl(Path(args.clean))
    sft = load_jsonl(Path(args.sft))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))["splits"]
    prompt_text = Path(args.prompt).read_text(encoding="utf-8")
    failures: list[str] = []
    warnings: list[str] = []

    expected_sft_records = sum(max(1, int(row.get("sft_repeats", 1))) for row in clean)
    if expected_sft_records != len(sft):
        fail(failures, f"clean/SFT exposure mismatch: expected {expected_sft_records}, found {len(sft)}")
    if len(clean) < args.min_records:
        fail(failures, f"clean set unexpectedly small: {len(clean)} < {args.min_records}")

    answers = Counter(row.get("answer") for row in clean)
    if set(answers) != set("ABCD") or max(answers.values()) - min(answers.values()) > 1:
        fail(failures, f"answer distribution not balanced: {dict(answers)}")

    arch = Counter(row.get("archetype") for row in clean)
    if set(arch) != {"CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE"}:
        fail(failures, f"unexpected archetypes: {dict(arch)}")

    train_ids = set(splits["TRAIN"]["source_ids"])
    heldout_ids = set(splits["LITMUS"]["source_ids"]) | set(splits["EVAL_HELDOUT"]["source_ids"])
    clean_source_ids = {row.get("source_id") for row in clean}
    genre_counts = Counter(source_genre(sources.get(sid), sid or "") for sid in clean_source_ids)
    speech_share = genre_counts.get("speech_or_argument", 0) / max(len(clean_source_ids), 1)
    if speech_share > 0.60:
        fail(
            failures,
            f"source genre skew: {genre_counts.get('speech_or_argument', 0)}/{len(clean_source_ids)} "
            "training sources are speeches/arguments; add laws, court opinions, treaties, and executive actions"
        )
    minimum_genres = {
        "court_opinion": 8,
        "law_or_constitution": 12,
        "treaty_or_compact": 3,
        "executive_action": 2,
    }
    for genre, minimum in minimum_genres.items():
        if genre_counts.get(genre, 0) < minimum:
            fail(failures, f"insufficient {genre} source coverage: {genre_counts.get(genre, 0)} < {minimum}")
    if len(clean_source_ids) < args.min_sources:
        fail(failures, f"insufficient source diversity: {len(clean_source_ids)} < {args.min_sources}")
    overlap = clean_source_ids & heldout_ids
    if overlap:
        fail(failures, f"training clean set overlaps heldout/litmus sources: {sorted(overlap)[:10]}")
    missing_train = clean_source_ids - train_ids
    if missing_train:
        fail(failures, f"clean set contains source ids outside TRAIN: {sorted(missing_train)[:10]}")

    bad_schema = []
    date_fails = []
    date_direction_counts: Counter[str] = Counter()
    verify_mismatch = []
    option_labels = []
    check_fails = Counter()
    synthesized_outside = 0
    normalized_outside = 0
    correlated_verifier = 0
    incomplete_semantic_review = 0
    quality_tiers: Counter[str] = Counter()
    seen_targets: set[tuple] = set()
    duplicate_targets = []
    for idx, row in enumerate(clean, 1):
        missing = REQUIRED_CLEAN_FIELDS - set(row)
        if missing:
            bad_schema.append((idx, "missing", sorted(missing)))
        if row.get("source_id") not in sources:
            bad_schema.append((idx, "missing_source", row.get("source_id")))
            continue
        prog = checks.run_checks(row, sources[row["source_id"]])
        date_direction_counts[str(prog.get("date_direction") or "unknown")] += 1
        for key in (
            "four_options", "one_key", "homogeneous_length", "schema_ok", "craft_ok", "disqualifying_ok",
        ):
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
        review = row.get("review") or {}
        if not review.get("current_rubric_complete"):
            incomplete_semantic_review += 1
        quality_tiers[str(row.get("quality_tier") or "unspecified")] += 1
        field_provenance = row.get("field_provenance") or {}
        if field_provenance.get("requires_outside_knowledge") == "normalized_from_keyed_development":
            normalized_outside += 1
        target_key = (
            row.get("source_id"),
            row.get("archetype"),
            str(row.get("stem") or "").strip().lower(),
            tuple(str(option).strip().lower() for option in (row.get("options") or [])),
        )
        if target_key in seen_targets:
            duplicate_targets.append((idx, row.get("source_id"), row.get("archetype")))
        seen_targets.add(target_key)
        answer = str(row.get("answer", "")).strip().upper()[:1]
        opts = row.get("options") or []
        if answer in "ABCD" and len(opts) == 4:
            legacy_em = f"{opts['ABCD'.index(answer)]} \u2014 {row.get('answer_dating', '')}".strip(" \u2014")
            legacy_hyphen = f"{opts['ABCD'.index(answer)]} - {row.get('answer_dating', '')}".strip(" -")
            if str(row.get("requires_outside_knowledge", "")).strip() in {legacy_em, legacy_hyphen}:
                synthesized_outside += 1
        row_options = row.get("options") or []
        loose_matches = [LOOSE_OPTION_LABEL.match(str(option)) for option in row_options]
        if (
            len(row_options) == 4
            and all(loose_matches)
            and {match.group(1) for match in loose_matches if match} == set("ABCD")
        ):
            option_labels.append((idx, "complete bare-label set"))
        for option in row_options:
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
    if duplicate_targets:
        fail(failures, f"duplicate SFT targets: {duplicate_targets[:5]}")
    if check_fails:
        fail(failures, f"programmatic check failures: {dict(check_fails)}")
    if synthesized_outside:
        warnings.append(
            f"{synthesized_outside}/{len(clean)} outside-knowledge explanations were mechanically "
            "backfilled from key+dating rather than preserved from generation"
        )
    if normalized_outside:
        warnings.append(
            f"{normalized_outside}/{len(clean)} legacy outside-knowledge fields were mechanically "
            "normalized to the keyed historical development"
        )
    if correlated_verifier:
        warnings.append(
            f"{correlated_verifier}/{len(clean)} records used the same model for judge and verifier"
        )
    if incomplete_semantic_review:
        warnings.append(
            f"{incomplete_semantic_review}/{len(clean)} records still need a full independent current-rubric semantic audit"
        )
    if (
        incomplete_semantic_review
        and quality_tiers.get("curated_causal_anchor", 0) < args.min_curated_anchors
    ):
        fail(failures, f"missing curated v4 anchors: {dict(quality_tiers)}")

    if '"options": ["A ...", "B ...", "C ...", "D ..."]' in prompt_text:
        fail(failures, "prompt still asks for labeled option strings")

    bad_sft = []
    sft_arch: Counter[str] = Counter()
    sft_answers: Counter[str] = Counter()
    sft_target_counts: Counter[tuple] = Counter()
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
        sft_arch[str(item.get("archetype"))] += 1
        sft_answers[str(item.get("answer"))] += 1
        sft_target_counts[(row.get("source_id"), item.get("archetype"), item.get("stem"))] += 1
        if REQUIRED_ITEM_FIELDS - set(item):
            bad_sft.append((idx, "assistant_missing_fields", sorted(REQUIRED_ITEM_FIELDS - set(item))))
        if any(OPTION_LABEL.search(str(option)) for option in item.get("options") or []):
            bad_sft.append((idx, "assistant_option_labels"))
        sft_options = item.get("options") or []
        sft_loose = [LOOSE_OPTION_LABEL.match(str(option)) for option in sft_options]
        if (
            len(sft_options) == 4
            and all(sft_loose)
            and {match.group(1) for match in sft_loose if match} == set("ABCD")
        ):
            bad_sft.append((idx, "assistant_bare_option_label_set"))
        completion = str(messages[-1].get("content", "")).strip()
        if not completion.startswith("[") or not completion.endswith("]"):
            bad_sft.append((idx, "assistant_not_strict_json_array"))
        if row.get("format_contract") != "json_array_v1":
            bad_sft.append((idx, "missing_format_contract"))
    if bad_sft:
        fail(failures, f"SFT issues: {bad_sft[:5]}")
    if set(sft_arch) != {"CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE"}:
        fail(failures, f"unexpected SFT archetypes: {dict(sft_arch)}")
    elif min(sft_arch.values()) / max(sft_arch.values()) < 0.9:
        fail(failures, f"effective SFT archetype imbalance too large: {dict(sft_arch)}")
    if set(sft_answers) != set("ABCD") or max(sft_answers.values()) - min(sft_answers.values()) > 1:
        fail(failures, f"effective SFT answer distribution not balanced: {dict(sft_answers)}")
    for row in clean:
        target = (row.get("source_id"), row.get("archetype"), row.get("stem"))
        expected = max(1, int(row.get("sft_repeats", 1)))
        if sft_target_counts[target] != expected:
            fail(failures, f"SFT repeat mismatch for {target}: {sft_target_counts[target]} vs {expected}")

    report = {
        "clean_records": len(clean),
        "sft_records": len(sft),
        "answer_distribution": dict(answers),
        "archetype_distribution": dict(arch),
        "effective_sft_archetype_distribution": dict(sft_arch),
        "effective_sft_answer_distribution": dict(sft_answers),
        "source_count": len(clean_source_ids),
        "source_genres": dict(genre_counts),
        "date_direction_distribution": dict(date_direction_counts),
        "quality_tiers": dict(quality_tiers),
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
