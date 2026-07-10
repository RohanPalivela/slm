#!/usr/bin/env python3
"""Build the v4 semantic-preservation dataset from v3 survivors and curated anchors.

The v3 run showed that broad SFT learned the output schema but did not reliably
improve historical discrimination. This builder deliberately reduces repeated
exposure to generic speeches, removes effect supervision from sources without a
defensible direct downstream consequence, and adds law, court, treaty, compact,
executive-action, and concrete-policy anchors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "train"))

import checks  # noqa: E402
from source_utils import source_genre  # noqa: E402
from audit_dataset import audit_record, normalize_options, rebalance_answers  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def stable_rank(row: dict) -> str:
    payload = "\n".join(
        str(row.get(key, ""))
        for key in ("source_id", "archetype", "stem", "answer_dating")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def keyed_option(row: dict) -> str:
    answer = str(row.get("answer", "")).strip().upper()[:1]
    options = row.get("options") or []
    if answer not in "ABCD" or len(options) != 4:
        return ""
    return str(options["ABCD".index(answer)]).strip().lower()


def keyed_option_display(row: dict) -> str:
    answer = str(row.get("answer", "")).strip().upper()[:1]
    options = row.get("options") or []
    if answer not in "ABCD" or len(options) != 4:
        return ""
    return str(options["ABCD".index(answer)]).strip()


def normalize_typography(value):
    if isinstance(value, str):
        return re.sub(r"\s*\u2014\s*", " - ", value)
    if isinstance(value, list):
        return [normalize_typography(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_typography(item) for key, item in value.items()}
    return value


def legacy_evidence_is_strict(row: dict) -> bool:
    """Use every quality signal that the archived v3 artifact actually saved.

    The archived judge object predates the current full rubric and therefore does
    not prove key correctness or uniqueness. Those missing dimensions are
    reported by the build and readiness validators instead of being invented.
    """
    judgment = row.get("judge") or {}
    verify = row.get("verify") or {}
    return bool(
        judgment.get("spec_adherence") == 2
        and judgment.get("distractor_craft") == 2
        and judgment.get("outside_knowledge_skill_fit") == 2
        and judgment.get("distractors_period_plausible") is True
        and verify.get("verified") is True
        and float(verify.get("agreement", 0.0)) == 1.0
        and int(verify.get("n_solved", 0)) >= 3
    )


def eligible_archetypes(source: dict, policy: dict) -> set[str]:
    source_id = source["id"]
    override = (policy.get("source_overrides") or {}).get(source_id)
    if override is not None:
        return set(override)
    genre = source_genre(source)
    return set((policy.get("defaults") or {}).get(genre, ["CAUSE_OF_SOURCE"]))


def select_diverse(rows: list[dict], limit: int) -> list[dict]:
    """Prefer distinct keyed developments, then fill deterministically."""
    selected: list[dict] = []
    seen_keys: set[str] = set()
    ordered = sorted(rows, key=stable_rank)
    for row in ordered:
        key = keyed_option(row)
        if key and key not in seen_keys:
            selected.append(row)
            seen_keys.add(key)
            if len(selected) == limit:
                return selected
    for row in ordered:
        if row not in selected:
            selected.append(row)
            if len(selected) == limit:
                break
    return selected


def build_anchor(claim: dict, source: dict) -> dict:
    distractors = claim.get("distractors") or []
    if len(distractors) != 3:
        raise ValueError(f"{claim.get('source_id')} {claim.get('archetype')}: need 3 distractors")
    traps = [str(d["trap"]).strip().upper() for d in distractors]
    row = {
        "source_id": source["id"],
        "archetype": claim["archetype"],
        "stem": claim["stem"],
        "options": [claim["key"], *[d["text"] for d in distractors]],
        "answer": "A",
        "answer_dating": claim["answer_dating"],
        "rationale": {
            "correct": claim["correct_rationale"],
            "A": "correct",
            "B": f"{traps[0]}: {distractors[0]['reason']}",
            "C": f"{traps[1]}: {distractors[1]['reason']}",
            "D": f"{traps[2]}: {distractors[2]['reason']}",
        },
        "trap_types": traps,
        "requires_outside_knowledge": claim["requires_outside_knowledge"],
        "period": source["period"],
        "themes": source["themes"],
        "dataset_version": "v4",
        "quality_tier": "curated_causal_anchor",
        "review": {
            "status": "curated_pending_independent_semantic_audit",
            "current_rubric_complete": False,
        },
        "provenance": {
            "generator": "v4_curated_causal_claims",
            "judge": None,
            "verifier": None,
        },
    }
    return row


def assign_balanced_sft_repeats(rows: list[dict]) -> None:
    """Assign the fewest repeat exposures that balance archetype and answer loss."""
    for row in rows:
        row["sft_repeats"] = 1
    archetypes = ("CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE")
    arch_counts = Counter(row["archetype"] for row in rows)
    answer_counts = Counter(row["answer"] for row in rows)
    candidates: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        candidates[(row["archetype"], row["answer"])].append(row)
    for group in candidates.values():
        group.sort(key=lambda row: (
            row.get("quality_tier") != "curated_causal_anchor",
            stable_rank(row),
        ))

    target_per_arch = max(arch_counts.values())
    if target_per_arch % 2:
        target_per_arch += 1
    allocation = None
    while allocation is None:
        per_answer_target = target_per_arch // 2
        answer_deficits = {
            answer: per_answer_target - answer_counts[answer]
            for answer in "ABCD"
        }
        arch_deficits = {
            archetype: target_per_arch - arch_counts[archetype]
            for archetype in archetypes
        }
        if all(value >= 0 for value in answer_deficits.values()):
            cause_target = arch_deficits["CAUSE_OF_SOURCE"]

            def search(index: int, cause_remaining: int, partial: dict[str, int]):
                if index == 4:
                    return dict(partial) if cause_remaining == 0 else None
                answer = "ABCD"[index]
                total = answer_deficits[answer]
                for cause_extra in range(total + 1):
                    effect_extra = total - cause_extra
                    if cause_extra and not candidates[("CAUSE_OF_SOURCE", answer)]:
                        continue
                    if effect_extra and not candidates[("EFFECT_OF_SOURCE", answer)]:
                        continue
                    if cause_extra > cause_remaining:
                        continue
                    partial[answer] = cause_extra
                    found = search(index + 1, cause_remaining - cause_extra, partial)
                    if found is not None:
                        return found
                partial.pop(answer, None)
                return None

            cause_by_answer = search(0, cause_target, {})
            if cause_by_answer is not None:
                allocation = {}
                for answer in "ABCD":
                    cause_extra = cause_by_answer[answer]
                    allocation[("CAUSE_OF_SOURCE", answer)] = cause_extra
                    allocation[("EFFECT_OF_SOURCE", answer)] = answer_deficits[answer] - cause_extra
                break
        target_per_arch += 2
        if target_per_arch > len(rows) * 2:
            raise ValueError("could not construct balanced SFT repeat allocation")

    for key, repeat_total in allocation.items():
        group = candidates[key]
        if repeat_total and not group:
            raise ValueError(f"no rows available for repeat allocation {key}")
        for index in range(repeat_total):
            group[index % len(group)]["sft_repeats"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", default=str(ROOT / "data/generated/train_clean.jsonl"))
    parser.add_argument("--claims", default=str(ROOT / "data/curated/v4_causal_claims.json"))
    parser.add_argument("--sources", default=str(ROOT / "data/seed_stimuli.jsonl"))
    parser.add_argument("--policy", default=str(ROOT / "data/training_archetype_policy.json"))
    parser.add_argument(
        "--legacy-effect-allowlist",
        default=str(ROOT / "data/curated/v4_legacy_effect_allowlist.json"),
    )
    parser.add_argument(
        "--legacy-cause-allowlist",
        default=str(ROOT / "data/curated/v4_legacy_cause_allowlist.json"),
    )
    parser.add_argument("--out", default=str(ROOT / "data/generated/train_v4_clean.jsonl"))
    parser.add_argument("--report", default=str(ROOT / "data/generated/train_v4_build_report.json"))
    parser.add_argument("--cause-per-source", type=int, default=1)
    parser.add_argument("--effect-per-source", type=int, default=5)
    args = parser.parse_args()

    sources = {row["id"]: row for row in load_jsonl(Path(args.sources))}
    legacy = load_jsonl(Path(args.legacy))
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8"))
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    effect_allowlist_obj = json.loads(Path(args.legacy_effect_allowlist).read_text(encoding="utf-8"))
    effect_allowlist = {
        (item["source_id"], item["stem"])
        for item in effect_allowlist_obj.get("items", [])
    }
    if len(effect_allowlist) != len(effect_allowlist_obj.get("items", [])):
        raise ValueError("duplicate entry in legacy effect allowlist")
    cause_allowlist_obj = json.loads(Path(args.legacy_cause_allowlist).read_text(encoding="utf-8"))
    cause_allowlist = {
        (item["source_id"], item["stem"])
        for item in cause_allowlist_obj.get("items", [])
    }
    if len(cause_allowlist) != len(cause_allowlist_obj.get("items", [])):
        raise ValueError("duplicate entry in legacy cause allowlist")

    strict_legacy = [row for row in legacy if legacy_evidence_is_strict(row)]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    policy_rejected = 0
    effect_review_rejected = 0
    cause_review_rejected = 0
    for row in strict_legacy:
        source = sources.get(row.get("source_id"))
        if source is None:
            continue
        if row.get("archetype") not in eligible_archetypes(source, policy):
            policy_rejected += 1
            continue
        if (
            row.get("archetype") == "EFFECT_OF_SOURCE"
            and (row["source_id"], row.get("stem")) not in effect_allowlist
        ):
            effect_review_rejected += 1
            continue
        if (
            row.get("archetype") == "CAUSE_OF_SOURCE"
            and (row["source_id"], row.get("stem")) not in cause_allowlist
        ):
            cause_review_rejected += 1
            continue
        grouped[(row["source_id"], row["archetype"])].append(row)

    selected_legacy: list[dict] = []
    for (source_id, archetype), rows in sorted(grouped.items()):
        limit = args.cause_per_source if archetype == "CAUSE_OF_SOURCE" else args.effect_per_source
        for original in select_diverse(rows, limit):
            row = dict(original)
            legacy_outside = row.get("requires_outside_knowledge")
            concise_outside = keyed_option_display(row)
            if concise_outside:
                row["legacy_requires_outside_knowledge"] = legacy_outside
                row["requires_outside_knowledge"] = concise_outside
                row["field_provenance"] = {
                    **(row.get("field_provenance") or {}),
                    "requires_outside_knowledge": "normalized_from_keyed_development",
                }
            row["dataset_version"] = "v4"
            row["quality_tier"] = "legacy_v3_strict_survivor"
            row["review"] = {
                "status": "legacy_partial_rubric_pending_independent_semantic_audit",
                "current_rubric_complete": False,
            }
            selected_legacy.append(row)

    selected_effect_keys = {
        (row["source_id"], row.get("stem"))
        for row in selected_legacy
        if row.get("archetype") == "EFFECT_OF_SOURCE"
    }
    if selected_effect_keys != effect_allowlist:
        missing = sorted(effect_allowlist - selected_effect_keys)
        extra = sorted(selected_effect_keys - effect_allowlist)
        raise ValueError(f"legacy effect allowlist mismatch: missing={missing[:3]} extra={extra[:3]}")
    selected_cause_keys = {
        (row["source_id"], row.get("stem"))
        for row in selected_legacy
        if row.get("archetype") == "CAUSE_OF_SOURCE"
    }
    if selected_cause_keys != cause_allowlist:
        missing = sorted(cause_allowlist - selected_cause_keys)
        extra = sorted(selected_cause_keys - cause_allowlist)
        raise ValueError(f"legacy cause allowlist mismatch: missing={missing[:3]} extra={extra[:3]}")

    anchors = []
    claim_keys: set[tuple[str, str]] = set()
    for claim in claims:
        key = (claim["source_id"], claim["archetype"])
        if key in claim_keys:
            raise ValueError(f"duplicate curated claim: {key}")
        claim_keys.add(key)
        source = sources.get(claim["source_id"])
        if source is None:
            raise ValueError(f"curated claim references missing source: {claim['source_id']}")
        if claim["archetype"] not in eligible_archetypes(source, policy):
            raise ValueError(f"curated claim violates archetype policy: {key}")
        anchors.append(build_anchor(claim, source))

    rows = [normalize_typography(row) for row in [*selected_legacy, *anchors]]
    rows = sorted(
        rows,
        key=lambda row: (row["source_id"], row["archetype"], stable_rank(row)),
    )
    for row in rows:
        normalize_options(row)
    rebalance_answers(rows)

    assign_balanced_sft_repeats(rows)

    audit_failures = []
    date_direction_counts: Counter[str] = Counter()
    for index, row in enumerate(rows, 1):
        source = sources[row["source_id"]]
        reasons = audit_record(row, source)
        prog = checks.run_checks(row, source)
        date_direction_counts[str(prog.get("date_direction") or "unknown")] += 1
        if (
            reasons
            or not prog.get("craft_ok")
            or not prog.get("disqualifying_ok")
            or not prog.get("homogeneous_length")
        ):
            audit_failures.append({
                "index": index,
                "source_id": row["source_id"],
                "archetype": row["archetype"],
                "reasons": reasons,
                "programmatic": prog,
            })
    if audit_failures:
        print(json.dumps(audit_failures[:10], indent=2, ensure_ascii=False))
        raise SystemExit(f"v4 build failed: {len(audit_failures)} record(s) failed post-build audit")

    source_ids = {row["source_id"] for row in rows}
    genre_counts = Counter(source_genre(sources[source_id]) for source_id in source_ids)
    report = {
        "dataset_version": "v4",
        "legacy_input_records": len(legacy),
        "legacy_strict_evidence_records": len(strict_legacy),
        "legacy_selected_records": len(selected_legacy),
        "legacy_policy_rejected_records": policy_rejected,
        "legacy_effect_review_rejected_records": effect_review_rejected,
        "legacy_cause_review_rejected_records": cause_review_rejected,
        "curated_anchor_records": len(anchors),
        "output_records": len(rows),
        "source_count": len(source_ids),
        "archetype_distribution": dict(Counter(row["archetype"] for row in rows)),
        "effective_sft_archetype_distribution": dict(Counter({
            archetype: sum(row["sft_repeats"] for row in rows if row["archetype"] == archetype)
            for archetype in ("CAUSE_OF_SOURCE", "EFFECT_OF_SOURCE")
        })),
        "answer_distribution": dict(Counter(row["answer"] for row in rows)),
        "effective_sft_answer_distribution": dict(Counter({
            answer: sum(row["sft_repeats"] for row in rows if row["answer"] == answer)
            for answer in "ABCD"
        })),
        "quality_tiers": dict(Counter(row["quality_tier"] for row in rows)),
        "source_genres": dict(genre_counts),
        "date_direction_distribution": dict(date_direction_counts),
        "known_limitations": [
            "The archived v3 records contain only the older partial judge dimensions.",
            "The archived v3 judge and verifier used the same model family.",
            "Legacy outside-knowledge fields were normalized mechanically from the keyed development.",
            "The curated v4 anchors have not yet received an independent model-family semantic audit.",
        ],
    }

    dump_jsonl(Path(args.out), rows)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"wrote {len(rows)} records -> {Path(args.out).relative_to(ROOT)}")
    print(f"wrote build report -> {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
