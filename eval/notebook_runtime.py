"""Runtime helpers for resumable, concurrent notebook evaluation.

The GPU notebook keeps model loading and generation inline because those pieces
are Colab-specific. This module owns the portable bookkeeping so checkpoint
files can be tested without loading Transformers or a model.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Iterable


def stable_hash(value: object) -> str:
    """Return a deterministic SHA-256 for a JSON-serializable value."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
