"""Runtime helpers for resumable, concurrent notebook evaluation.

The GPU notebook keeps model loading and generation inline because those pieces
are Colab-specific. This module owns the portable bookkeeping so checkpoint
files can be tested without loading Transformers or a model.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable, Mapping


def stable_hash(value: object) -> str:
    """Return a deterministic SHA-256 for a JSON-serializable value."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def attempt_seed(
    base_seed: int,
    run: int,
    source_id: str,
    archetype: str,
    *,
    namespace: str = "eval",
) -> int:
    """Return a matched, independently replayable seed for one prompt attempt."""
    payload = {
        "namespace": namespace,
        "base_seed": int(base_seed),
        "run": int(run),
        "source_id": str(source_id),
        "archetype": str(archetype),
    }
    # Stay inside the signed 63-bit range accepted by CPU and CUDA generators.
    return int(stable_hash(payload)[:16], 16) % (2**63 - 1)


def attempt_key(row: dict) -> tuple[str, int, str, str]:
    """Identify one model generation attempt."""
    return (
        str(row["model"]),
        int(row["run"]),
        str(row["source_id"]),
        str(row["archetype"]),
    )


def score_key(row: dict) -> tuple[str, int, str, str, int, str]:
    """Identify one parsed item sent to the semantic judge."""
    return (
        *attempt_key(row),
        int(row["item_index"]),
        str(row["item_sha256"]),
    )


def _prompt_key(row: dict) -> tuple[int, str, str]:
    archetype = row.get("archetype")
    if archetype is None and isinstance(row.get("item"), dict):
        archetype = row["item"].get(
            "_requested_archetype",
            row["item"].get("archetype"),
        )
    return (int(row["run"]), str(row["source_id"]), str(archetype))


def attempt_contract_outcome(
    attempt: dict,
    scored_rows: Iterable[dict] = (),
) -> dict:
    """Reduce one raw attempt plus its item rows to fail-closed outcomes.

    Tolerantly recovered or multiple items remain available for diagnostics, but
    they cannot receive item-level "any passed" credit. Judge-unavailable items
    fail attempted-prompt certification and are counted separately.
    """
    rows = list(scored_rows)
    diagnostics = attempt.get("format") or {}
    exact_contract = bool(
        diagnostics.get(
            "exact_contract_valid",
            (
                diagnostics.get("strict_array_contract", False)
                and attempt.get("n_items") == 1
                and not diagnostics.get("contains_think_tag", False)
            ),
        )
    )
    exact_one_generated = attempt.get("n_items", len(rows)) == 1
    exact_one_row = len(rows) == 1 and exact_one_generated
    row = rows[0] if exact_one_row else None
    attempt_schema = attempt.get("schema") or {}
    schema_valid = bool(
        exact_one_generated
        and (
            (row.get("prog") or {}).get(
                "schema_valid",
                (row.get("prog") or {}).get("schema_ok", False),
            )
            if row
            else attempt_schema.get(
                "schema_valid",
                attempt_schema.get("schema_ok", False),
            )
        )
    )
    finish_reason = attempt.get("finish_reason")
    generation_complete = finish_reason != "max_new_tokens"
    product_contract_valid = bool(
        exact_contract and exact_one_generated and schema_valid and generation_complete
    )

    judgment = row.get("judge") if row else None
    judge_available = bool(
        row
        and (
            row.get("near_miss") is not None
            or (
                isinstance(judgment, dict)
                and judgment.get("_status", "ok") == "ok"
            )
        )
    )
    judge_unavailable = bool(row and isinstance(judgment, dict) and not judge_available)

    metric_sources = {
        "expert_grade": "expert_grade",
        "near_miss": "near_miss",
        "key_valid": "key_valid",
        "label_clean": "label_clean",
    }
    metric_values: dict[str, bool | None] = {}
    for output_name, row_name in metric_sources.items():
        value = row.get(row_name) if row else None
        if output_name == "label_clean" and row and value is None:
            value = row.get("distillable_item_valid")
        metric_values[output_name] = bool(product_contract_valid and value is True)
        metric_values[f"{output_name}_resolved"] = (
            bool(product_contract_valid and value is True)
            if judge_available
            else None
        )

    return {
        "prompt_key": _prompt_key(attempt),
        "parse_success": bool(attempt.get("n_items", 0) > 0),
        "strict_top_level_array": bool(
            diagnostics.get(
                "strict_top_level_array",
                diagnostics.get("strict_array_contract", False),
            )
        ),
        "exact_contract": exact_contract,
        "schema_valid": schema_valid,
        "generation_complete": generation_complete,
        "product_contract_valid": product_contract_valid,
        "judge_available": judge_available,
        "judge_unavailable": judge_unavailable,
        **metric_values,
    }


def aggregate_attempt_metrics(
    attempts: Iterable[dict],
    scored_rows: Iterable[dict] = (),
) -> dict:
    """Aggregate product and quality rates over all attempted prompts."""
    materialized_attempts = list(attempts)
    rows_by_key: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    for row in scored_rows:
        rows_by_key[_prompt_key(row)].append(row)
    outcomes = [
        attempt_contract_outcome(attempt, rows_by_key.get(_prompt_key(attempt), ()))
        for attempt in materialized_attempts
    ]
    total = len(outcomes)

    def count_true(name: str) -> int:
        return sum(outcome.get(name) is True for outcome in outcomes)

    def attempted_rate(name: str) -> float | None:
        return count_true(name) / total if total else None

    resolved = [outcome for outcome in outcomes if outcome["judge_available"]]

    def resolved_rate(name: str) -> float | None:
        key = f"{name}_resolved"
        values = [outcome[key] for outcome in resolved if outcome.get(key) is not None]
        return sum(value is True for value in values) / len(values) if values else None

    format_buckets = Counter(
        (attempt.get("format") or {}).get("bucket", "unknown")
        for attempt in materialized_attempts
    )
    result = {
        "attempted_prompts": total,
        "parsed_attempts": count_true("parse_success"),
        "exact_contract_successes": count_true("exact_contract"),
        "schema_valid_successes": count_true("schema_valid"),
        "product_contract_successes": count_true("product_contract_valid"),
        "successfully_judged_attempts": count_true("judge_available"),
        "judge_unavailable_attempts": count_true("judge_unavailable"),
        "parse_success_rate": attempted_rate("parse_success"),
        "strict_top_level_array_rate": attempted_rate("strict_top_level_array"),
        "exact_contract_rate": attempted_rate("exact_contract"),
        "schema_valid_rate": attempted_rate("schema_valid"),
        "product_contract_rate": attempted_rate("product_contract_valid"),
        "format_buckets": dict(format_buckets),
    }
    for metric in ("expert_grade", "near_miss", "key_valid", "label_clean"):
        result[f"attempted_prompt_{metric}_rate"] = attempted_rate(metric)
        result[f"{metric}_per_successfully_judged_attempt"] = resolved_rate(metric)

    # Historical names remain available to older reports and artifact readers.
    result["strict_array_rate"] = result["strict_top_level_array_rate"]
    result["attempted_prompt_near_miss_lower_bound"] = result[
        "attempted_prompt_near_miss_rate"
    ]
    result["attempted_prompt_distillable_item_valid_rate"] = result[
        "attempted_prompt_label_clean_rate"
    ]
    return result


def source_clustered_paired_ci(
    base_outcomes: Mapping[tuple, bool | None],
    tuned_outcomes: Mapping[tuple, bool | None],
    *,
    draws: int = 10_000,
    seed: int = 42,
) -> dict:
    """Bootstrap a tuned-minus-base CI after averaging within source clusters."""
    paired = sorted(
        key
        for key in set(base_outcomes) & set(tuned_outcomes)
        if base_outcomes[key] is not None and tuned_outcomes[key] is not None
    )
    by_source: dict[str, list[int]] = defaultdict(list)
    for key in paired:
        if len(key) < 3:
            raise ValueError("paired outcome keys must contain run, source_id, archetype")
        source_id = str(key[-2])
        by_source[source_id].append(
            int(bool(tuned_outcomes[key])) - int(bool(base_outcomes[key]))
        )
    source_deltas = [sum(values) / len(values) for values in by_source.values()]
    if not source_deltas:
        return {
            "paired_prompts": 0,
            "sources": 0,
            "mean_delta": None,
            "bootstrap_95_ci": None,
        }
    if draws < 2:
        raise ValueError("draws must be at least 2")
    rng = random.Random(seed)
    n_sources = len(source_deltas)
    bootstrap = sorted(
        sum(rng.choice(source_deltas) for _ in range(n_sources)) / n_sources
        for _ in range(draws)
    )
    low_index = int(0.025 * draws)
    high_index = min(draws - 1, int(0.975 * draws))
    return {
        "paired_prompts": len(paired),
        "sources": n_sources,
        "mean_delta": sum(source_deltas) / n_sources,
        "bootstrap_95_ci": [bootstrap[low_index], bootstrap[high_index]],
    }


def append_jsonl_group(path: str | Path, rows: Iterable[dict]) -> None:
    """Durably append a group as one line.

    One line per group prevents a partial write from preserving only part of an
    HF repetition batch. A truncated final line is ignored when resuming.
    """
    materialized = list(rows)
    if not materialized:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps({"rows": materialized}, ensure_ascii=False) + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            # Some mounted notebook filesystems do not expose fsync.
            pass


def load_jsonl_groups(path: str | Path) -> tuple[list[dict], int]:
    """Load complete checkpoint groups and count ignored corrupt lines."""
    target = Path(path)
    if not target.exists():
        return [], 0
    rows: list[dict] = []
    ignored = 0
    with target.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                group = json.loads(line)
            except json.JSONDecodeError:
                ignored += 1
                continue
            group_rows = group.get("rows") if isinstance(group, dict) else None
            if not isinstance(group_rows, list) or not all(
                isinstance(row, dict) for row in group_rows
            ):
                ignored += 1
                continue
            rows.extend(group_rows)
    return rows, ignored


def dedupe_rows(rows: Iterable[dict], key: Callable[[dict], tuple]) -> dict[tuple, dict]:
    """Return the last complete checkpoint row for each logical key."""
    return {key(row): row for row in rows}


def runs_for_model(model: dict, candidate_runs: int, teacher_runs: int) -> int:
    """Use repeated candidate samples while keeping the teacher as a reference."""
    return teacher_runs if model.get("kind") == "api_teacher" else candidate_runs
