#!/usr/bin/env python3
"""
Manually calibrate the LLM judge against a human ground truth (the G-cal gate,
docs/plan_v2 M2.5) — WITHOUT any model calls. Works on items the harness already
generated + judged (results/litmus_items.jsonl).

The litmus verdict hinges on subjective judge dimensions — chiefly
`distractors_period_plausible` (which drags `spec_adherence` to 1 and produces the
RETHINK). This tool lets you check whether the judge is biased on those calls.

Workflow
--------
1. EXPORT a blind, stratified sample (judge verdict + model rationale stripped):

       python eval/calibrate.py export --n 30

   Writes results/calibration_blind.jsonl (you fill this in) and a hidden
   results/calibration_key.jsonl (the judge's verdicts — do NOT open while grading).

2. GRADE by hand: open results/calibration_blind.jsonl and, for each item, fill the
   "human" object using ONLY the source + stem + options + keyed letter:
       key_historically_correct   true|false
       key_uniquely_best          true|false
       distractors_period_plausible true|false   (the one that matters most)
       spec_adherence             0|1|2
   Leave "notes" for anything you want to remember. Ungraded rows (nulls) are skipped.

3. SCORE agreement (judge vs you), per dimension, with direction + Cohen's kappa:

       python eval/calibrate.py score

Read the "how should I calibrate" guidance for what the numbers mean; the headline
gate is >=90% agreement on key_valid, and whether the judge tracks you on
distractors_period_plausible (if the judge is much harsher, the low expert-grade —
and the RETHINK — is a judge artifact, not a real ceiling).
"""
from __future__ import annotations
import argparse
import json
import os
import random
import shutil
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Dimensions a human grades. Booleans + one ordinal (spec_adherence 0/1/2).
BOOL_DIMS = ("key_historically_correct", "key_uniquely_best", "distractors_period_plausible")
ORD_DIMS = ("spec_adherence",)
HUMAN_DIMS = BOOL_DIMS + ORD_DIMS

BLIND_PATH = os.path.join(ROOT, "results", "calibration_blind.jsonl")
KEY_PATH = os.path.join(ROOT, "results", "calibration_key.jsonl")


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _sources_by_id():
    path = os.path.join(ROOT, "data", "seed_stimuli.jsonl")
    return {s["id"]: s for s in _load_jsonl(path)}


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #

def _stratified_sample(items, n, seed):
    """Oversample the disputed boundary: bucket by the judge's spec_adherence so
    the sample spans clear-pass (2), soft-fail (1), and hard-fail (0) instead of
    being dominated by whichever the model produced most."""
    rng = random.Random(seed)
    buckets = {0: [], 1: [], 2: []}
    for it in items:
        s = int((it.get("judge") or {}).get("spec_adherence", 0))
        buckets.get(s, buckets[0]).append(it)
    for b in buckets.values():
        rng.shuffle(b)
    # target mix leans toward the spec==1 boundary (where plausibility fights live)
    targets = {2: round(n * 0.34), 1: round(n * 0.50), 0: n - round(n * 0.34) - round(n * 0.50)}
    picked = []
    for s in (2, 1, 0):
        picked += buckets[s][:targets[s]]
    # backfill from any leftover if a bucket was short
    if len(picked) < n:
        leftover = [it for s in (1, 2, 0) for it in buckets[s][targets[s]:]]
        picked += leftover[:n - len(picked)]
    rng.shuffle(picked)  # hide strata order from the grader
    return picked[:n]


def cmd_export(args):
    items = _load_jsonl(args.path)
    items = [r for r in items if r.get("judge")]  # need a judge verdict to compare
    if args.model:
        items = [r for r in items if args.model.lower() in r["model"].lower()]
    elif args.role:
        items = [r for r in items if r.get("role") == args.role]
    if not items:
        raise SystemExit("no judged items match the filter (try --role candidate or --model ...)")

    if os.path.exists(BLIND_PATH) and not args.force:
        graded = sum(1 for r in _load_jsonl(BLIND_PATH)
                     if any(v is not None for v in r.get("human", {}).values()
                            if not isinstance(v, str)))
        if graded:
            raise SystemExit(f"{BLIND_PATH} already has {graded} graded rows; pass --force to overwrite")

    sample = _stratified_sample(items, args.n, args.seed)
    srcs = _sources_by_id()

    with open(BLIND_PATH, "w", encoding="utf-8") as fb, open(KEY_PATH, "w", encoding="utf-8") as fk:
        for cid, r in enumerate(sample, 1):
            src = srcs.get(r["source_id"], {})
            # Blind row: everything a grader needs, NOTHING that reveals the verdict
            # or the model's own reasoning (rationale/trap_types are anchors).
            fb.write(json.dumps({
                "cal_id": cid,
                "source_id": r["source_id"],
                "archetype": r.get("archetype"),
                "attribution": src.get("attribution", ""),
                "source_text": src.get("text", ""),
                "stem": r.get("stem"),
                "options": r.get("options"),
                "answer": r.get("answer"),
                "human": {
                    "key_historically_correct": None,
                    "key_uniquely_best": None,
                    "distractors_period_plausible": None,
                    "spec_adherence": None,
                    "notes": "",
                },
            }, ensure_ascii=False) + "\n")
            j = r["judge"]
            fk.write(json.dumps({
                "cal_id": cid,
                "model": r["model"],
                "source_id": r["source_id"],
                "archetype": r.get("archetype"),
                "judge": {k: j.get(k) for k in HUMAN_DIMS},
                "judge_key_valid": bool(j.get("key_historically_correct") and j.get("key_uniquely_best")),
                "judge_notes": j.get("notes", ""),
            }, ensure_ascii=False) + "\n")

    print(f"wrote {len(sample)} blind items -> {os.path.relpath(BLIND_PATH, ROOT)}")
    print(f"hidden judge key       -> {os.path.relpath(KEY_PATH, ROOT)}  (do NOT open while grading)")
    print("\nNext: grade each row's \"human\" object (source + stem + options + keyed letter ONLY),")
    print("then run:  python eval/calibrate.py score")


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #

def _cohen_kappa(pairs):
    """Cohen's kappa for a list of (judge, human) category pairs."""
    n = len(pairs)
    if n == 0:
        return None
    cats = sorted({c for pr in pairs for c in pr})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for c in cats:
        pj = sum(1 for a, _ in pairs if a == c) / n
        ph = sum(1 for _, b in pairs if b == c) / n
        pe += pj * ph
    if pe >= 1.0:  # perfect chance agreement (only one category present)
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def _fully_graded(h):
    return all(h.get(d) is not None for d in HUMAN_DIMS)


def cmd_score(args):
    if not os.path.exists(BLIND_PATH) or not os.path.exists(KEY_PATH):
        raise SystemExit("run `export` and grade results/calibration_blind.jsonl first")
    blind = {r["cal_id"]: r for r in _load_jsonl(BLIND_PATH)}
    key = {r["cal_id"]: r for r in _load_jsonl(KEY_PATH)}

    rows = []
    for cid, b in blind.items():
        h = b.get("human", {})
        if cid in key and _fully_graded(h):
            rows.append((cid, key[cid], h))
    if not rows:
        raise SystemExit("no fully-graded rows found — fill in the \"human\" objects in "
                         f"{os.path.relpath(BLIND_PATH, ROOT)} (all of {', '.join(HUMAN_DIMS)})")

    print(f"Calibration: {len(rows)}/{len(blind)} items graded\n")
    print(f"{'dimension':30} {'agree':>7} {'kappa':>7} {'judge-strict':>13} {'judge-lenient':>14}")
    print("-" * 74)

    def report(name, pairs, positive_is_good=True):
        n = len(pairs)
        agree = sum(1 for a, b in pairs if a == b) / n
        kappa = _cohen_kappa(pairs)
        # "strict" = judge withheld a positive the human gave; "lenient" = opposite.
        strict = sum(1 for a, b in pairs if a is False and b is True)
        lenient = sum(1 for a, b in pairs if a is True and b is False)
        kp = "n/a" if kappa is None else f"{kappa:+.2f}"
        print(f"{name:30} {agree:>6.0%} {kp:>7} {strict:>13} {lenient:>14}")
        return agree

    # boolean dims
    for d in BOOL_DIMS:
        pairs = [(bool(k["judge"][d]), bool(h[d])) for _, k, h in rows]
        report(d, pairs)

    # key_valid (the plan's >=90% gate) = historically_correct AND uniquely_best
    kv_pairs = [(bool(k["judge_key_valid"]),
                 bool(h["key_historically_correct"]) and bool(h["key_uniquely_best"]))
                for _, k, h in rows]
    kv_agree = report("key_valid (GATE)", kv_pairs)

    # spec_adherence: exact-match agreement + the ==2 boundary the metric keys on
    spec_pairs = [(int(k["judge"]["spec_adherence"]), int(h["spec_adherence"])) for _, k, h in rows]
    n = len(spec_pairs)
    spec_exact = sum(1 for a, b in spec_pairs if a == b) / n
    spec_kappa = _cohen_kappa(spec_pairs)
    spec2_pairs = [(a == 2, b == 2) for a, b in spec_pairs]
    spec2_strict = sum(1 for a, b in spec2_pairs if a is False and b is True)
    spec2_lenient = sum(1 for a, b in spec2_pairs if a is True and b is False)
    print(f"{'spec_adherence (exact 0/1/2)':30} {spec_exact:>6.0%} "
          f"{spec_kappa:>+7.2f} {'':>13} {'':>14}")
    print(f"{'  spec==2 (expert boundary)':30} "
          f"{sum(1 for a,b in spec2_pairs if a==b)/n:>6.0%} {'':>7} "
          f"{spec2_strict:>13} {spec2_lenient:>14}")

    print("\nLegend: judge-strict = judge said FALSE/no-2 where you said TRUE/2 "
          "(judge too harsh); judge-lenient = the reverse.")

    # verdict
    print("\n" + "=" * 74)
    gate = "PASS" if kv_agree >= 0.90 else "FAIL"
    print(f"key_valid agreement = {kv_agree:.0%}  -> G-cal gate (>=90%): {gate}")
    plaus = [(bool(k["judge"]["distractors_period_plausible"]),
              bool(h["distractors_period_plausible"])) for _, k, h in rows]
    p_strict = sum(1 for a, b in plaus if a is False and b is True)
    if p_strict >= max(2, 0.2 * len(rows)):
        print(f"NOTE: judge withheld 'period-plausible' on {p_strict}/{len(rows)} items you passed — "
              "judge looks HARSH on distractors; the low expert-grade / RETHINK may be a judge "
              "artifact. Consider few-shotting the judge or reporting near_miss.")
    print("=" * 74)

    if args.show_disagreements:
        print("\nDisagreements (judge vs you):")
        for cid, k, h in rows:
            diffs = []
            for d in BOOL_DIMS:
                if bool(k["judge"][d]) != bool(h[d]):
                    diffs.append(f"{d}: judge={bool(k['judge'][d])} you={bool(h[d])}")
            if int(k["judge"]["spec_adherence"]) != int(h["spec_adherence"]):
                diffs.append(f"spec: judge={k['judge']['spec_adherence']} you={h['spec_adherence']}")
            if diffs:
                print(f"  #{cid} {k['source_id']} [{k.get('archetype')}]")
                for d in diffs:
                    print(f"      {d}")
                if k.get("judge_notes"):
                    print(f"      judge note: {k['judge_notes']}")


# --------------------------------------------------------------------------- #
# rejudge — re-run the (recalibrated) judge over the graded gold items only
# --------------------------------------------------------------------------- #

def cmd_rejudge(args):
    """Re-judge the graded calibration items with the CURRENT judge prompt/config
    and overwrite results/calibration_key.jsonl, so `score` reflects a judge you
    just edited — without re-running the whole harness. Recovers each item's full
    text (incl. rationale/answer_dating, which the blind file strips) from
    results/litmus_items.jsonl."""
    import judge  # local import: only this command needs the model stack

    if not os.path.exists(BLIND_PATH) or not os.path.exists(KEY_PATH):
        raise SystemExit("run `export` and grade first")
    blind = {r["cal_id"]: r for r in _load_jsonl(BLIND_PATH)}
    key = {r["cal_id"]: r for r in _load_jsonl(KEY_PATH)}

    if not os.path.exists(args.models):
        raise SystemExit(f"judge config not found: {args.models}")
    judge_cfg = json.load(open(args.models)).get("judge")
    if not judge_cfg:
        raise SystemExit("no 'judge' configured in the models file")

    # index full items so we can restore rationale/answer_dating for the judge
    full = {}
    for r in _load_jsonl(args.path):
        full[(r["model"], r["source_id"], r.get("stem"))] = r
    srcs = _sources_by_id()

    targets = [cid for cid, b in blind.items() if _fully_graded(b.get("human", {}))] \
        if not args.all else list(blind)
    if not targets:
        raise SystemExit("no graded items to re-judge (grade some first, or pass --all)")

    print(f"re-judging {len(targets)} items with judge '{judge_cfg.get('name')}' ...")
    HUMAN = HUMAN_DIMS
    for n, cid in enumerate(targets, 1):
        k = key[cid]
        rec = full.get((k["model"], k["source_id"], blind[cid].get("stem")))
        if not rec:
            print(f"  #{cid}: could not recover full item, skipping")
            continue
        item = {"archetype": rec.get("archetype"), "stem": rec.get("stem"),
                "options": rec.get("options"), "answer": rec.get("answer"),
                "answer_dating": rec.get("answer_dating"), "rationale": rec.get("rationale")}
        j = judge.judge_item(judge_cfg, srcs.get(k["source_id"], {}), item, role="teacher")
        k["judge"] = {d: j.get(d) for d in HUMAN}
        k["judge_key_valid"] = bool(j.get("key_historically_correct") and j.get("key_uniquely_best"))
        k["judge_notes"] = j.get("notes", "")
        print(f"  [{n}/{len(targets)}] #{cid} {k['source_id']}: "
              f"plausible={j.get('distractors_period_plausible')} spec={j.get('spec_adherence')}")

    with open(KEY_PATH, "w", encoding="utf-8") as f:
        for cid in sorted(key):
            f.write(json.dumps(key[cid], ensure_ascii=False) + "\n")
    print(f"\nrewrote {os.path.relpath(KEY_PATH, ROOT)}. Now run:  python eval/calibrate.py score --show-disagreements")


# --------------------------------------------------------------------------- #
# grade (interactive)
# --------------------------------------------------------------------------- #

RUBRIC = """\
You are grading each question the way a strict AP U.S. History committee reviewer
would, using ONLY the source + the question + the keyed (correct) letter. Decide
each field:

  key_historically_correct   Is the keyed answer factually true history?  [y/n]
  key_uniquely_best           Is it the SINGLE best answer (no other option is
                              also defensibly correct)?                    [y/n]
  distractors_period_plausible  Are ALL 3 wrong options era-plausible traps a
                              shaky-but-knowledgeable student would consider?
                              Say NO if even one is a "giveaway" you can rule out
                              in ~1 second purely because it is obviously the
                              wrong century or an obviously unrelated topic.  [y/n]
  spec_adherence              Overall craft: 2 = fully expert-grade, 1 = usable
                              but a soft wobble (usually one weak distractor),
                              0 = a disqualifying flaw.                     [0/1/2]

Grade on the RULE above, not gut feel — that is what makes this a calibration.
At any prompt: [b]ack  [s]kip  [q]save & quit."""

_QUIT, _BACK, _SKIP = object(), object(), object()


def _termwidth():
    return min(shutil.get_terminal_size((100, 24)).columns, 100)


def _wrap(text, indent=""):
    w = _termwidth()
    return textwrap.fill(text or "", width=w, initial_indent=indent,
                         subsequent_indent=indent) or indent


def _ask(prompt, current, validate):
    """Prompt until a valid value (or a nav command) is entered. Empty input keeps
    `current` if one exists. Returns the parsed value or a _QUIT/_BACK/_SKIP token."""
    cur = "" if current is None else f" (current: {current})"
    while True:
        try:
            raw = input(f"    {prompt}{cur}: ").strip()
        except EOFError:
            print()
            return _QUIT
        low = raw.lower()
        if low in ("q", "quit"):
            return _QUIT
        if low in ("b", "back"):
            return _BACK
        if low in ("s", "skip"):
            return _SKIP
        if raw == "" and current is not None:
            return current
        val = validate(low)
        if val is not None:
            return val
        print("      ? enter y/n (or 0/1/2), or b/s/q")


def _yn(s):
    if s in ("y", "yes", "true", "t", "1"):
        return True
    if s in ("n", "no", "false", "f", "0"):
        return False
    return None


def _spec(s):
    return int(s) if s in ("0", "1", "2") else None


def _render_item(r, idx, total, graded):
    w = _termwidth()
    print("\n" + "=" * w)
    print(f"ITEM {idx + 1}/{total}   (graded so far: {graded})   cal_id={r['cal_id']}   "
          f"archetype={r.get('archetype')}")
    print("-" * w)
    print("SOURCE — " + (r.get("attribution") or ""))
    print(_wrap(r.get("source_text", ""), indent="  "))
    print("\nQUESTION:")
    print(_wrap(r.get("stem", ""), indent="  "))
    ans = str(r.get("answer", "")).strip().upper()[:1]
    print()
    for i, o in enumerate(r.get("options") or []):
        letter = "ABCD"[i] if i < 4 else "?"
        mark = "  <== KEYED (correct)" if letter == ans else ""
        print(_wrap(f"{letter}) {o}", indent="  ") + mark)
    print("-" * w)


def _grade_one(r, idx, total, graded):
    _render_item(r, idx, total, graded)
    h = r.setdefault("human", {})
    steps = [
        ("key_historically_correct", "keyed answer factually correct?  [y/n]", _yn),
        ("key_uniquely_best", "keyed answer the single best?  [y/n]", _yn),
        ("distractors_period_plausible", "all 3 distractors era-plausible (no giveaways)?  [y/n]", _yn),
        ("spec_adherence", "overall craft  [0/1/2]", _spec),
    ]
    for field, prompt, validate in steps:
        val = _ask(prompt, h.get(field), validate)
        if val is _QUIT:
            return _QUIT
        if val is _BACK:
            return _BACK
        if val is _SKIP:
            return _SKIP
        h[field] = val
    try:
        note = input("    notes (optional, enter to skip): ").strip()
    except EOFError:
        note = ""
    if note:
        h["notes"] = note
    return None  # advance


def cmd_grade(args):
    if not os.path.exists(BLIND_PATH):
        raise SystemExit("run `export` first (no blind file to grade)")
    rows = _load_jsonl(BLIND_PATH)

    def save():
        with open(BLIND_PATH, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ndone = lambda: sum(1 for r in rows if _fully_graded(r.get("human", {})))
    # resume at the first ungraded item unless --regrade
    start = 0
    if not args.regrade:
        while start < len(rows) and _fully_graded(rows[start].get("human", {})):
            start += 1
        if start >= len(rows):
            print(f"all {len(rows)} items already graded. Re-grade with --regrade, "
                  "or score with:  python eval/calibrate.py score")
            return

    print(RUBRIC)
    i = start
    while 0 <= i < len(rows):
        action = _grade_one(rows[i], i, len(rows), ndone())
        save()  # persist after every item so nothing is lost
        if action is _QUIT:
            break
        if action is _BACK:
            i = max(0, i - 1)
        else:  # advance (graded or skipped)
            i += 1

    save()
    done = ndone()
    print(f"\nsaved: {done}/{len(rows)} items graded -> {os.path.relpath(BLIND_PATH, ROOT)}")
    if done:
        print("score it with:  python eval/calibrate.py score --show-disagreements")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="write a blind, stratified sample to grade")
    pe.add_argument("--path", default=os.path.join(ROOT, "results", "litmus_items.jsonl"))
    pe.add_argument("--n", type=int, default=30, help="items to sample")
    pe.add_argument("--role", default="teacher", help="filter by role (teacher/candidate); ignored if --model set")
    pe.add_argument("--model", default=None, help="filter by model-name substring")
    pe.add_argument("--seed", type=int, default=0, help="sampling seed (reproducible)")
    pe.add_argument("--force", action="store_true", help="overwrite an existing graded blind file")
    pe.set_defaults(func=cmd_export)

    pg = sub.add_parser("grade", help="interactively grade the blind sample in the terminal")
    pg.add_argument("--regrade", action="store_true", help="revisit already-graded items instead of resuming at the first ungraded one")
    pg.set_defaults(func=cmd_grade)

    pr = sub.add_parser("rejudge", help="re-run the current judge over the graded gold items (verify a judge edit without a full harness run)")
    pr.add_argument("--models", default=os.path.join(HERE, "models.json"), help="model config JSON (for the judge)")
    pr.add_argument("--path", default=os.path.join(ROOT, "results", "litmus_items.jsonl"), help="source of full item text")
    pr.add_argument("--all", action="store_true", help="re-judge every sampled item, not just the graded ones")
    pr.set_defaults(func=cmd_rejudge)

    ps = sub.add_parser("score", help="score judge-vs-human agreement on the graded sample")
    ps.add_argument("--show-disagreements", action="store_true", help="list every item you and the judge disagree on")
    ps.set_defaults(func=cmd_score)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
