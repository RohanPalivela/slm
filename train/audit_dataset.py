#!/usr/bin/env python3
"""
Audit generated APUSH training records and optionally build a strict clean set.

This catches defects that can pass a judge but poison SFT:
- prompt/target schema mismatch (`requires_outside_knowledge` missing)
- option labels embedded inside option text (`A. ...`)
- incomplete trap_types lists when rationales still expose the labels
- cause/effect direction contradictions in stems or answer_dating

The cleaner is intentionally conservative. It applies mechanical repairs, but
quarantines direction-confused records rather than rewriting history content.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from date_utils import date_spans, source_year  # noqa: E402

VALID_TRAPS = {"WRONG_ERA", "TRUE_BUT_IRRELEVANT", "SCOPE_MISMATCH", "PARTIALLY_TRUE"}
OPTION_LABEL = re.compile(r"^\s*[A-D][).:]\s+")
LOOSE_OPTION_LABEL = re.compile(r"^\s*([A-D])(?:[).:]\s+|\s+(?=[A-Z]))")
TRAP_RE = re.compile(
    r"^\s*(WRONG_ERA|TRUE_BUT_IRRELEVANT|SCOPE_MISMATCH|PARTIALLY_TRUE)\b",
    re.I,
)

# These are high-precision enough to flag training poison, but they are not a
# substitute for historical review. Quarantined rows should be regenerated.
CAUSE_WITH_EFFECT_STEM = re.compile(
    r"\b("
    r"most immediately led to|"
    r"immediately led to|"
    r"led to which|"
    r"contributed most directly to which|"
    r"contributed most directly to which of the following|"
    r"resulted in|"
    r"gave rise to|"
    r"inaugurated a program that most immediately led"
    r")\b",
    re.I,
)
EFFECT_WITH_CAUSE_STEM = re.compile(
    r"\b("
    r"was most directly a response to|"
    r"made possible most directly by|"
    r"was made possible most directly by|"
    r"drew most directly on|"
    r"was most directly shaped by"
    r")\b",
    re.I,
)
CAUSE_BAD_DATING = re.compile(
    r"\b("
    r"postdates?|"
    r"effect direction|"
    r"flows? from (?:the )?(?:source|excerpt|address|speech|rhetoric|concern)|"
    r"following (?:the|this) .*?(?:source|excerpt|address|speech)|"
    r"immediately follows (?:the|this) .*?(?:source|excerpt|address|speech)|"
    r"postdat(?:e|es|ing) (?:the|this) .*?(?:source|excerpt|address|speech)"
    r")\b",
    re.I,
)
EFFECT_BAD_DATING = re.compile(
    r"\b("
    r"predates?|"
    r"cause-before-source|"
    r"before (?:the|this) .*?(?:source|excerpt|address|speech)|"
    r"prior to (?:the|this) .*?(?:source|excerpt|address|speech)|"
    r"earlier than (?:the|this) .*?(?:source|excerpt|address|speech)"
    r")\b",
    re.I,
)
EFFECT_CONTEMPORANEOUS = re.compile(
    r"\b("
    r"same[- ]year|"
    r"contemporaneous|"
    r"at the time|"
    r"ongoing|"
    r"itself|"
    r"same (?:ordinance|statute|law|speech|address|event)"
    r")\b",
    re.I,
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_trap_types(rec: dict) -> list[str] | None:
    answer = str(rec.get("answer", "")).strip().upper()[:1]
    rationale = rec.get("rationale")
    if answer not in "ABCD" or not isinstance(rationale, dict):
        return None
    traps: list[str] = []
    for label in "ABCD":
        if label == answer:
            continue
        match = TRAP_RE.search(str(rationale.get(label, "")))
        if not match:
            return None
        traps.append(match.group(1).upper())
    return traps if len(traps) == 3 else None


def years_in(text: str) -> list[int]:
    return [end for _, end in date_spans(text or "")]


def keyed_option(rec: dict) -> str:
    answer = str(rec.get("answer", "")).strip().upper()[:1]
    options = rec.get("options") or []
    if answer not in "ABCD":
        return ""
    idx = "ABCD".index(answer)
    if idx >= len(options):
        return ""
    return str(options[idx])


def add_requires_outside_knowledge(rec: dict) -> None:
    if rec.get("requires_outside_knowledge"):
        return
    keyed = OPTION_LABEL.sub("", keyed_option(rec)).strip()
    dating = str(rec.get("answer_dating") or "").strip()
    if keyed and dating:
        rec["requires_outside_knowledge"] = f"{keyed} - {dating}"
    elif keyed:
        rec["requires_outside_knowledge"] = keyed


def normalize_options(rec: dict) -> int:
    options = rec.get("options")
    if not isinstance(options, list):
        return 0
    original_keyed = keyed_option(rec)
    changed = 0
    loose_matches = [LOOSE_OPTION_LABEL.match(str(option)) for option in options]
    has_complete_loose_label_set = bool(
        len(options) == 4
        and all(loose_matches)
        and {match.group(1) for match in loose_matches if match} == set("ABCD")
    )
    clean = []
    for option in options:
        text = str(option)
        pattern = LOOSE_OPTION_LABEL if has_complete_loose_label_set else OPTION_LABEL
        stripped = pattern.sub("", text).strip()
        if stripped != text:
            changed += 1
        clean.append(stripped)
    rec["options"] = clean
    outside = str(rec.get("requires_outside_knowledge") or "")
    if has_complete_loose_label_set and original_keyed and outside.startswith(original_keyed):
        cleaned_keyed = LOOSE_OPTION_LABEL.sub("", original_keyed).strip()
        rec["requires_outside_knowledge"] = cleaned_keyed + outside[len(original_keyed):]
    return changed


def audit_record(rec: dict, source: dict | None = None) -> list[str]:
    reasons: list[str] = []
    arch = rec.get("archetype")
    stem = str(rec.get("stem") or "")
    dating = str(rec.get("answer_dating") or "")
    options = rec.get("options")
    answer = str(rec.get("answer", "")).strip().upper()[:1]
    traps = rec.get("trap_types")
    rationale = rec.get("rationale")
    sy = source_year(source)
    dated_spans = date_spans(dating)
    non_source_spans = [
        (start, end) for start, end in dated_spans
        if sy is None or not (start == end == sy)
    ]

    if arch not in {"CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE"}:
        reasons.append("bad_archetype")
    if not isinstance(options, list) or len(options) != 4:
        reasons.append("bad_options")
    if answer not in "ABCD":
        reasons.append("bad_answer")
    if not isinstance(rationale, dict) or not all(k in rationale for k in ("correct", "A", "B", "C", "D")):
        reasons.append("bad_rationale")
    elif answer in "ABCD" and str(rationale.get(answer, "")).strip().lower().rstrip(".") != "correct":
        reasons.append("key_rationale_not_correct")

    if not rec.get("requires_outside_knowledge"):
        reasons.append("missing_requires_outside_knowledge")

    if not isinstance(traps, list) or len(traps) != 3:
        reasons.append("bad_trap_count")
    elif any(str(t).strip().upper() not in VALID_TRAPS for t in traps):
        reasons.append("bad_trap_label")
    elif len(set(str(t).strip().upper() for t in traps)) < 2:
        reasons.append("low_trap_diversity")
    elif sum(1 for t in traps if str(t).strip().upper() == "WRONG_ERA") > 1:
        reasons.append("too_many_wrong_era")
    elif infer_trap_types(rec) and [str(t).strip().upper() for t in traps] != infer_trap_types(rec):
        reasons.append("trap_types_conflict_with_rationales")

    if arch == "CAUSE_OF_SOURCE":
        if CAUSE_WITH_EFFECT_STEM.search(stem):
            reasons.append("cause_record_has_effect_stem")
        if CAUSE_BAD_DATING.search(dating):
            reasons.append("cause_record_has_effect_dating_language")
        if sy is not None and non_source_spans and min(start for start, _ in non_source_spans) > sy:
            reasons.append("cause_answer_dates_after_source")
    elif arch == "EFFECT_OF_SOURCE":
        if EFFECT_WITH_CAUSE_STEM.search(stem):
            reasons.append("effect_record_has_cause_stem")
        if EFFECT_BAD_DATING.search(dating):
            reasons.append("effect_record_has_cause_dating_language")
        if sy is not None and non_source_spans and max(end for _, end in non_source_spans) <= sy:
            reasons.append("effect_answer_not_explicitly_later")
        if EFFECT_CONTEMPORANEOUS.search(dating):
            reasons.append("effect_contemporaneous_needs_review")

    return reasons


def rebalance_answers(rows: list[dict]) -> int:
    """Deterministically shuffle options so keys are balanced A/B/C/D.

    The generator had a severe position artifact (nearly every answer was A).
    This keeps each item's same options and rationales, but moves the keyed
    option to a rotating target letter and remaps A/B/C/D rationales plus
    trap_types to match the new option order.
    """
    changed = 0
    for i, rec in enumerate(rows):
        old_answer = str(rec.get("answer", "")).strip().upper()[:1]
        options = rec.get("options")
        rationale = rec.get("rationale")
        if old_answer not in "ABCD" or not isinstance(options, list) or len(options) != 4:
            continue
        if not isinstance(rationale, dict):
            continue

        target_answer = "ABCD"[i % 4]
        old_key_idx = "ABCD".index(old_answer)
        new_key_idx = "ABCD".index(target_answer)
        old_wrong = [idx for idx in range(4) if idx != old_key_idx]

        new_to_old: list[int | None] = [None, None, None, None]
        new_to_old[new_key_idx] = old_key_idx
        for new_idx, old_idx in zip([idx for idx in range(4) if idx != new_key_idx], old_wrong):
            new_to_old[new_idx] = old_idx

        if new_to_old == [0, 1, 2, 3] and old_answer == target_answer:
            continue

        old_rationale = dict(rationale)
        rec["options"] = [options[old_idx] for old_idx in new_to_old if old_idx is not None]
        rec["answer"] = target_answer

        new_rationale = {"correct": old_rationale.get("correct", "")}
        for new_idx, old_idx in enumerate(new_to_old):
            old_label = "ABCD"[old_idx]
            new_label = "ABCD"[new_idx]
            new_rationale[new_label] = old_rationale.get(old_label, "")
        new_rationale[target_answer] = "correct"
        rec["rationale"] = new_rationale

        inferred = infer_trap_types(rec)
        if inferred:
            rec["trap_types"] = inferred

        verify = rec.get("verify")
        if isinstance(verify, dict):
            verify["key"] = target_answer
            if "votes" in verify:
                agreement = verify.get("agreement")
                n_solved = verify.get("n_solved")
                if isinstance(n_solved, int) and n_solved > 0 and agreement == 1.0:
                    verify["votes"] = {target_answer: n_solved}
                elif isinstance(verify.get("votes"), dict):
                    verify["votes"] = {
                        target_answer if str(k).strip().upper()[:1] == old_answer else k: v
                        for k, v in verify["votes"].items()
                    }

        changed += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(ROOT / "data/generated/train.jsonl"))
    ap.add_argument("--clean-out", default=str(ROOT / "data/generated/train_clean.jsonl"))
    ap.add_argument("--quarantine-out", default=str(ROOT / "data/generated/train_quarantine.jsonl"))
    ap.add_argument("--report-out", default=str(ROOT / "data/generated/train_audit_report.json"))
    ap.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    ap.add_argument(
        "--backfill-outside-knowledge", action="store_true",
        help="legacy-only: synthesize a missing field from key+dating; normally quarantine it",
    )
    ap.add_argument("--write-clean", action="store_true")
    args = ap.parse_args()

    rows = load_jsonl(Path(args.inp))
    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    clean: list[dict] = []
    quarantine: list[dict] = []
    reason_counts: Counter[str] = Counter()
    repair_counts: Counter[str] = Counter()
    examples: dict[str, list[dict]] = defaultdict(list)

    for line_no, original in enumerate(rows, 1):
        rec = dict(original)
        labeled = normalize_options(rec)
        if labeled:
            repair_counts["stripped_option_labels"] += 1

        if args.backfill_outside_knowledge and not rec.get("requires_outside_knowledge"):
            add_requires_outside_knowledge(rec)
            if rec.get("requires_outside_knowledge"):
                repair_counts["added_requires_outside_knowledge"] += 1

        traps = rec.get("trap_types")
        inferred = infer_trap_types(rec)
        normalized_traps = [str(t).strip().upper() for t in traps] if isinstance(traps, list) else None
        if inferred and normalized_traps != inferred:
            rec["trap_types"] = inferred
            if not isinstance(traps, list) or len(traps) != 3:
                repair_counts["inferred_trap_types"] += 1
            else:
                repair_counts["corrected_trap_types_from_rationales"] += 1

        reasons = audit_record(rec, sources.get(rec.get("source_id")))
        if reasons:
            for reason in reasons:
                reason_counts[reason] += 1
                if len(examples[reason]) < 8:
                    examples[reason].append({
                        "line": line_no,
                        "source_id": original.get("source_id"),
                        "archetype": original.get("archetype"),
                        "stem": original.get("stem"),
                    })
            quarantine.append({
                "line": line_no,
                "reasons": reasons,
                "record": rec,
            })
        else:
            clean.append(rec)

    # Balance answer positions only after quarantine decisions so the final clean
    # set has a near-uniform key distribution without trying to salvage bad rows.
    answer_shuffled = rebalance_answers(clean)
    if answer_shuffled:
        repair_counts["answer_position_rebalanced"] = answer_shuffled

    # Re-audit after shuffling as a guard against rationale/trap remapping bugs.
    post_shuffle_quarantine: list[dict] = []
    post_shuffle_clean: list[dict] = []
    for idx, rec in enumerate(clean, 1):
        reasons = audit_record(rec, sources.get(rec.get("source_id")))
        if reasons:
            for reason in reasons:
                reason_counts[f"post_shuffle_{reason}"] += 1
            post_shuffle_quarantine.append({
                "line": None,
                "reasons": [f"post_shuffle_{reason}" for reason in reasons],
                "record": rec,
            })
        else:
            post_shuffle_clean.append(rec)
    if post_shuffle_quarantine:
        quarantine.extend(post_shuffle_quarantine)
        clean = post_shuffle_clean

    report = {
        "input": os.path.relpath(args.inp, ROOT),
        "total_records": len(rows),
        "clean_records": len(clean),
        "quarantined_records": len(quarantine),
        "answer_distribution": dict(Counter(rec.get("answer") for rec in clean)),
        "repair_counts": dict(repair_counts),
        "reason_counts": dict(reason_counts),
        "examples": examples,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.write_clean:
        dump_jsonl(Path(args.clean_out), clean)
        dump_jsonl(Path(args.quarantine_out), quarantine)
        Path(args.report_out).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(clean)} clean records -> {os.path.relpath(args.clean_out, ROOT)}")
        print(f"wrote {len(quarantine)} quarantined records -> {os.path.relpath(args.quarantine_out, ROOT)}")
        print(f"wrote report -> {os.path.relpath(args.report_out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
