#!/usr/bin/env python3
"""
Dataset factory for generating APUSH training candidates. For each
(stimulus, archetype), it generates with the teacher, repairs
the distractors, then runs the 3-stage filter and KEEPS only survivors, looping
until it hits the per-slot target (or an attempt cap):

    generate (teacher)
      -> repair distractors (same model)
      -> Stage A  programmatic checks (checks.py; free)      fail => trash
      -> Stage B  judge near-miss / expert-quality           fail => trash
      -> Stage C  key-verifier (independent solve, k-of-n)   fail => trash
      -> keep

No per-item human grading. The per-stage yields it prints double as the G-yield
calibration: run it on a small target first, read the funnel, then scale
volume/budget from the measured keep rate.

Quick start:
    python eval/generate.py --split TRAIN --target 6 --repair            # real
    python eval/generate.py --split TRAIN --target 2 --limit 3 --dry-run # smoke
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import providers          # noqa: E402
import checks             # noqa: E402
import judge              # noqa: E402
import repair             # noqa: E402
import verifier           # noqa: E402
from prompt_loader import (  # noqa: E402
    LitmusPrompt,
    canonicalize_item_archetype,
    extract_items,
    generation_format_diagnostics,
)
from harness import load_sources, DEFAULT_ARCHETYPES, DIFFICULTY, dry_run_models  # noqa: E402
from source_utils import source_genre  # noqa: E402


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(payload)


def _sha256_file(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def _sanitize_config_value(value, key: str = ""):
    sensitive_parts = ("password", "secret", "api_key", "access_token")
    lowered = key.lower()
    if any(part in lowered for part in sensitive_parts) and not lowered.endswith("_env"):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            child_key: _sanitize_config_value(child_value, child_key)
            for child_key, child_value in value.items()
            if not child_key.startswith("_")
        }
    if isinstance(value, list):
        return [_sanitize_config_value(child) for child in value]
    return value


def _sanitized_model_config(cfg: dict) -> dict:
    """Keep inference settings while excluding comments and literal credentials."""
    return _sanitize_config_value(cfg)


def _model_metadata(cfg: dict) -> dict:
    clean = _sanitized_model_config(cfg)
    return {
        "name": cfg.get("name"),
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "revision": cfg.get("revision") or cfg.get("model_revision"),
        "adapter": cfg.get("adapter"),
        "adapter_revision": cfg.get("adapter_revision"),
        "config": clean,
        "config_sha256": _sha256_json(clean),
    }


def _stage_a_failure_reasons(prog: dict) -> list[str]:
    reasons = []
    for key in (
        "four_options",
        "one_key",
        "no_all_none_absolute",
        "trap_count_3",
        "trap_types_valid",
        "trap_diversity_ge2",
        "wrong_era_le1",
        "no_parenthetical_option_dates",
        "rationale_complete",
        "rationale_marks_key",
    ):
        if not prog.get(key):
            reasons.append(f"failed_{key}")
    if prog.get("source_leak"):
        reasons.append("failed_source_leak")
    if prog.get("date_direction") == "fail":
        reasons.append("failed_date_direction")
    return reasons or ["failed_programmatic_gate"]


def _eligible_archetypes(source: dict, policy: dict) -> set[str]:
    override = (policy.get("source_overrides") or {}).get(source["id"])
    if override is not None:
        return set(override)
    return set((policy.get("defaults") or {}).get(source_genre(source), ["CAUSE_OF_SOURCE"]))


def _stage_a(item, source):
    prog = checks.run_checks(item, source)
    return (prog["disqualifying_ok"] and prog["craft_ok"]), prog


class Funnel:
    """Thread-safe filter-funnel counters (also the G-yield report)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.c = {"generated": 0, "pass_a": 0, "pass_b": 0, "pass_c": 0, "kept": 0}

    def add(self, **kw):
        with self.lock:
            for k, v in kw.items():
                self.c[k] += v

    def report(self):
        c = self.c
        def rate(a, b):
            return f"{(a / b):.0%}" if b else "n/a"
        return (
            f"  generated : {c['generated']}\n"
            f"  Stage A (checks)   kept {c['pass_a']:4d}  ({rate(c['pass_a'], c['generated'])} of generated)\n"
            f"  Stage B (judge)    kept {c['pass_b']:4d}  ({rate(c['pass_b'], c['pass_a'])} of A)\n"
            f"  Stage C (verifier) kept {c['pass_c']:4d}  ({rate(c['pass_c'], c['pass_b'])} of B)\n"
            f"  KEPT (net)         {c['kept']:4d}  ({rate(c['kept'], c['generated'])} net keep)"
        )


def run_slot(
    source,
    archetype,
    *,
    gen_cfg,
    judge_cfg,
    ver_cfg,
    prompt,
    cfg,
    funnel,
    lock,
    out_records,
    out_attempts,
):
    """Generate-to-target for one (source, archetype). Returns kept records."""
    kept = []
    attempts = 0
    while len(kept) < cfg["target"] and attempts < cfg["cap"]:
        attempts += 1
        system, user = prompt.build(
            source=source["text"], attribution=source.get("attribution", ""), note="",
            n=cfg["n"], archetypes=archetype, difficulty=DIFFICULTY,
            include_fewshot=cfg["fewshot"])
        raw = ""
        error = None
        try:
            raw = providers.generate(gen_cfg, system, user, cfg["temperature"], role="teacher")
            items = extract_items(raw)
        except providers.ProviderError as exc:
            items = []
            error = str(exc)
        attempt_id = f"{source['id']}:{archetype}:{attempts}"
        attempt_record = {
            "attempt_id": attempt_id,
            "source_id": source["id"],
            "archetype": archetype,
            "slot_attempt": attempts,
            "requested_n": cfg["n"],
            "target_per_slot": cfg["target"],
            "generator": _model_metadata(gen_cfg),
            "request": {
                "system": system,
                "user": user,
                "sha256": _sha256_text(system + "\n\0\n" + user),
            },
            "raw": raw,
            "provider_error": error,
            "format": generation_format_diagnostics(raw),
            "parsed_item_count": len(items),
            "call_status": (
                "provider_error" if error else "parsed" if items else "no_parseable_items"
            ),
            "item_decisions": [],
        }
        funnel.add(generated=len(items))
        for item_index, model_item in enumerate(items):
            decision = {
                "item_index": item_index,
                "model_item": model_item,
                "repair": {"requested": bool(cfg["repair"]), "accepted": False},
                "stage_a": {"status": "not_run", "passed": None, "reasons": []},
                "stage_b": {"status": "not_run", "passed": None, "reasons": []},
                "stage_c": {"status": "not_run", "passed": None, "reasons": []},
                "final_decision": "not_evaluated",
                "rejection_reasons": [],
            }
            if len(kept) >= cfg["target"]:
                decision["rejection_reasons"] = ["slot_target_already_reached"]
                attempt_record["item_decisions"].append(decision)
                continue
            it = canonicalize_item_archetype(model_item, requested_archetype=archetype)
            if cfg["repair"]:
                it, repair_trace = repair.repair_item_with_trace(
                    gen_cfg,
                    source,
                    it,
                    cfg["temperature"],
                    role="teacher",
                )
                decision["repair"] = {"requested": True, **repair_trace}
                it = canonicalize_item_archetype(it, requested_archetype=archetype)
            decision["evaluated_item"] = it
            ok_a, prog = _stage_a(it, source)
            stage_a_reasons = [] if ok_a else _stage_a_failure_reasons(prog)
            decision["stage_a"] = {
                "status": "passed" if ok_a else "failed",
                "passed": ok_a,
                "reasons": stage_a_reasons,
                "programmatic": prog,
            }
            if not ok_a:
                decision["final_decision"] = "rejected"
                decision["rejection_reasons"] = stage_a_reasons
                attempt_record["item_decisions"].append(decision)
                continue
            funnel.add(pass_a=1)
            if cfg["dry_run"]:
                j = judge._mock_judgment("teacher") if hasattr(judge, "_mock_judgment") else None
                j = judge._normalize(j)
            else:
                j = judge.judge_item(judge_cfg, source, it, role="teacher")
            near = judge.near_grade(prog["disqualifying_ok"] and prog["craft_ok"], j)
            if near is None:
                stage_b_reasons = [f"judge_{j.get('_status', 'unavailable')}"]
            elif not near:
                stage_b_reasons = ["judge_near_grade_failed"]
            else:
                stage_b_reasons = []
            decision["stage_b"] = {
                "status": "passed" if near is True else "inconclusive" if near is None else "failed",
                "passed": near,
                "reasons": stage_b_reasons,
                "judgment": j,
            }
            if near is not True:
                decision["final_decision"] = "rejected"
                decision["rejection_reasons"] = stage_b_reasons
                attempt_record["item_decisions"].append(decision)
                continue
            funnel.add(pass_b=1)
            if cfg["dry_run"]:
                v = {
                    "verified": True,
                    "key": it.get("answer", "A"),
                    "threshold": cfg["verify_threshold"],
                    "requested_solves": cfg["verify_n"],
                    "agreement": 1.0,
                    "votes": {it.get("answer", "A"): cfg["verify_n"]},
                    "n_solved": cfg["verify_n"],
                    "attempts": [],
                }
            else:
                v = verifier.verify_item(
                    ver_cfg,
                    source,
                    it,
                    n=cfg["verify_n"],
                    threshold=cfg["verify_threshold"],
                )
            if v["verified"]:
                stage_c_reasons = []
            elif not v.get("n_solved"):
                stage_c_reasons = ["verifier_no_valid_votes"]
            else:
                stage_c_reasons = ["verifier_key_agreement_failed"]
            decision["stage_c"] = {
                "status": "passed" if v["verified"] else "failed",
                "passed": bool(v["verified"]),
                "reasons": stage_c_reasons,
                "verification": v,
            }
            if not v["verified"]:
                decision["final_decision"] = "rejected"
                decision["rejection_reasons"] = stage_c_reasons
                attempt_record["item_decisions"].append(decision)
                continue
            funnel.add(pass_c=1, kept=1)
            decision["final_decision"] = "kept"
            decision["kept_index_in_slot"] = len(kept)
            attempt_record["item_decisions"].append(decision)
            kept.append({
                "source_id": source["id"], "archetype": it.get("archetype"),
                "stem": it.get("stem"), "options": it.get("options"),
                "answer": it.get("answer"), "answer_dating": it.get("answer_dating"),
                "rationale": it.get("rationale"), "trap_types": it.get("trap_types"),
                "requires_outside_knowledge": it.get("requires_outside_knowledge"),
                "period": source.get("period"), "themes": source.get("themes"),
                # Preserve the full decision, not just display dimensions. This
                # makes later rubric audits and failure analysis reproducible.
                "judge": dict(j),
                "verify": v, "repaired": bool(it.get("_repaired")),
                "provenance": {"generator": gen_cfg["name"], "judge": judge_cfg.get("name"),
                               "verifier": ver_cfg.get("name"), "attempts": attempts,
                               "attempt_id": attempt_id, "item_index": item_index,
                               "request_sha256": attempt_record["request"]["sha256"]},
            })
        with lock:
            out_attempts.append(attempt_record)
    with lock:
        out_records.extend(kept)
    status = "OK " if len(kept) >= cfg["target"] else "SHORT"
    sys.stdout.write(f"  [{status}] {source['id']:28} {archetype:16} kept {len(kept)}/{cfg['target']} "
                     f"({attempts} attempt(s))\n")
    sys.stdout.flush()
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=os.path.join(HERE, "models.json"))
    ap.add_argument("--split", default="TRAIN", help="which split's sources to generate on")
    ap.add_argument("--target", type=int, default=6, help="kept items per (source, archetype)")
    ap.add_argument("--cap", type=int, default=4, help="max generation attempts per slot")
    ap.add_argument("--n", type=int, default=6, help="items requested per generation call")
    ap.add_argument("--verify-n", type=int, default=3, help="independent solves per item (key-verifier)")
    ap.add_argument(
        "--verify-threshold",
        type=float,
        default=1.0,
        help="required verifier agreement with the key (default 1.0, unanimous)",
    )
    ap.add_argument("--repair", action="store_true", help="run the distractor-repair pass (recommended)")
    ap.add_argument("--fewshot", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--archetypes", default=DEFAULT_ARCHETYPES)
    ap.add_argument("--limit", type=int, default=0, help="limit number of sources (smoke test)")
    ap.add_argument("--concurrency", type=int, default=6, help="parallel (source,archetype) slots")
    ap.add_argument(
        "--archetype-policy",
        default=os.path.join(ROOT, "data", "training_archetype_policy.json"),
        help="training-only source/archetype eligibility policy",
    )
    ap.add_argument(
        "--ignore-archetype-policy",
        action="store_true",
        help="generate every requested archetype even when a source has no approved direct causal path",
    )
    ap.add_argument("--dry-run", action="store_true", help="mock generator/judge/verifier (no keys/network)")
    ap.add_argument(
        "--allow-correlated-verifier",
        action="store_true",
        help="unsafe legacy escape hatch: allow the judge or generator model to also solve keys",
    )
    ap.add_argument("--out", default=None, help="output jsonl (default data/generated/<split>.jsonl)")
    ap.add_argument(
        "--attempts-out",
        default=None,
        help="raw calls and per-item filter decisions (default beside --out)",
    )
    args = ap.parse_args()
    if args.target < 1 or args.cap < 1 or args.n < 1 or args.verify_n < 1:
        ap.error("--target, --cap, --n, and --verify-n must all be positive")
    if not 0.0 < args.verify_threshold <= 1.0:
        ap.error("--verify-threshold must be greater than 0 and at most 1")
    if args.concurrency < 1:
        ap.error("--concurrency must be positive")

    if args.dry_run:
        models = dry_run_models()
        gen_cfg = models["teacher"]
        judge_cfg = models["judge"]
        ver_cfg = models["judge"]
    else:
        if not os.path.exists(args.models):
            raise SystemExit(f"model config not found: {args.models}")
        models = _load_json(args.models)
        gen_cfg = models.get("generator") or models.get("teacher")
        judge_cfg = models.get("judge")
        ver_cfg = models.get("verifier") or judge_cfg
        if not gen_cfg or not judge_cfg:
            raise SystemExit("need a 'teacher'/'generator' and a 'judge' in the models file")
        identities = {
            "generator": (gen_cfg.get("provider"), gen_cfg.get("model")),
            "judge": (judge_cfg.get("provider"), judge_cfg.get("model")),
            "verifier": (ver_cfg.get("provider"), ver_cfg.get("model")),
        }
        correlated = (
            not models.get("verifier")
            or identities["verifier"] == identities["judge"]
            or identities["verifier"] == identities["generator"]
        )
        if correlated and not args.allow_correlated_verifier:
            raise SystemExit(
                "bulk generation requires a separately configured verifier model family; "
                "the archived v3 set used correlated judge/verifier votes. Add models.verifier "
                "or pass --allow-correlated-verifier only for a diagnostic run."
            )
        if correlated:
            print("WARNING: correlated verifier explicitly allowed; do not treat these records as independently verified.")

    sources = load_sources(args.split)
    if args.limit:
        sources = sources[:args.limit]
    if not sources:
        raise SystemExit(f"split {args.split!r} has no sources. Expand the corpus (A3) and "
                         "repopulate data/splits.json (TRAIN is empty by default).")
    archs = [a.strip() for a in args.archetypes.split(",") if a.strip()]
    policy = None
    if args.split == "TRAIN" and not args.ignore_archetype_policy:
        if not os.path.exists(args.archetype_policy):
            raise SystemExit(f"training archetype policy not found: {args.archetype_policy}")
        policy = _load_json(args.archetype_policy)

    prompt_path = os.path.join(ROOT, "prompts", "litmus_generation_prompt.md")
    source_path = os.path.join(ROOT, "data", "seed_stimuli.jsonl")
    split_path = os.path.join(ROOT, "data", "splits.json")
    prompt = LitmusPrompt.from_file(prompt_path)
    cfg = {"target": args.target, "cap": args.cap, "n": args.n, "repair": args.repair,
           "fewshot": args.fewshot, "temperature": args.temperature, "verify_n": args.verify_n,
           "verify_threshold": args.verify_threshold, "dry_run": args.dry_run}

    funnel = Funnel()
    out_records, out_attempts, lock = [], [], threading.Lock()
    slots = [
        (source, archetype)
        for source in sources
        for archetype in archs
        if policy is None or archetype in _eligible_archetypes(source, policy)
    ]
    skipped_slots = len(sources) * len(archs) - len(slots)
    print(f"generating {len(slots)} slots ({len(sources)} sources x {len(archs)} archetypes), "
          f"target {args.target}/slot, cap {args.cap}"
          + (" [DRY-RUN]" if args.dry_run else "") + (" +repair" if args.repair else "")
          + (f"; skipped {skipped_slots} weak-causality slot(s) by policy" if skipped_slots else ""))
    t0 = time.time()
    workers = 1 if (gen_cfg.get("provider") in ("ollama", "mock")) else args.concurrency
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_slot, s, a, gen_cfg=gen_cfg, judge_cfg=judge_cfg, ver_cfg=ver_cfg,
                          prompt=prompt, cfg=cfg, funnel=funnel, lock=lock,
                          out_records=out_records, out_attempts=out_attempts)
                for s, a in slots]
        for f in cf.as_completed(futs):
            f.result()

    out_path = args.out or os.path.join(ROOT, "data", "generated", f"{args.split.lower()}.jsonl")
    _ensure_parent(out_path)
    out_records.sort(key=lambda row: (
        row["source_id"],
        row["archetype"],
        row["provenance"]["attempts"],
        row["provenance"]["item_index"],
    ))
    out_attempts.sort(key=lambda row: (
        row["source_id"], row["archetype"], row["slot_attempt"]
    ))
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    model_metadata = {
        "generator": _model_metadata(gen_cfg),
        "judge": _model_metadata(judge_cfg),
        "verifier": _model_metadata(ver_cfg),
    }
    meta = {
        "schema_version": "training_generation_v2",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": args.split,
        "archetypes": archs,
        "target_per_slot": args.target,
        "attempted_generation_calls": len(out_attempts),
        "parsed_candidates": funnel.c["generated"],
        "kept": len(out_records),
        "elapsed_s": round(time.time() - t0, 1),
        "dry_run": args.dry_run,
        "repair": args.repair,
        "verify_n": args.verify_n,
        "verify_threshold": args.verify_threshold,
        "models": model_metadata,
        "archetype_policy": None if policy is None else os.path.relpath(args.archetype_policy, ROOT),
        "skipped_policy_slots": skipped_slots,
        "revision_hashes": {
            "generator_config_sha256": model_metadata["generator"]["config_sha256"],
            "judge_config_sha256": model_metadata["judge"]["config_sha256"],
            "verifier_config_sha256": model_metadata["verifier"]["config_sha256"],
            "models_file_sha256": None if args.dry_run else _sha256_file(args.models),
            "prompt_file_sha256": _sha256_file(prompt_path),
            "archetype_policy_sha256": (
                _sha256_file(args.archetype_policy) if policy is not None else None
            ),
            "source_corpus_sha256": _sha256_file(source_path),
            "split_manifest_sha256": _sha256_file(split_path),
            "selected_sources_sha256": _sha256_json(sources),
        },
    }
    meta_path = out_path[:-6] + "_meta.json" if out_path.endswith(".jsonl") else out_path + "_meta.json"
    attempts_path = args.attempts_out or (
        out_path[:-6] + "_attempts.json" if out_path.endswith(".jsonl") else out_path + "_attempts.json"
    )
    _ensure_parent(attempts_path)
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with open(attempts_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "schema_version": "training_generation_attempts_v1",
                "metadata": meta,
                "attempts": out_attempts,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")

    print("\n" + "=" * 60)
    print("FILTER FUNNEL (also your G-yield):")
    print(funnel.report())
    print(f"\nkept {len(out_records)} items -> {out_path}")
    print(f"saved {len(out_attempts)} raw attempt trace(s) -> {attempts_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
