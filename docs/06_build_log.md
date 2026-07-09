# Build Log — What's Been Done (in plain terms)

> A running journal of the project: what we tried, what failed, what we changed,
> and what finally worked. This is a **process log**, not a results brochure —
> the point is to show the reasoning and the dead ends, not just the final numbers.
> Training results get appended at the end once the model finishes.

**The goal in one sentence:** teach a small model (Qwen3‑4B) to turn a historical
source into an *expert‑grade* AP U.S. History multiple‑choice question — the kind
with four tempting-but-wrong answers, not the obvious junk LLMs usually write.

---

## 1. Problem generation & research

**What we were trying to figure out:** what actually makes an APUSH question "hard"
and "human," so we could aim the model at a real, checkable skill instead of a vague
"write good questions."

- **Deep-researched the question taxonomy** (`docs/01_apush_question_taxonomy.md`,
  `taxonomy/apush_question_archetypes.json`). Broke real APUSH stimulus questions
  down into 5 families / 12 archetypes, a fixed menu of question stems, and — the
  important bit — a **closed menu of 4 distractor "traps"**: `wrong_era`,
  `true_but_irrelevant`, `scope_mismatch`, `partially_true`. This is the core
  insight: a good wrong answer is *true*, just not the *best* answer to *this*
  question.
- **Ran a feasibility assessment** (`docs/03_feasibility_assessment.md`). Verdict:
  **BUILD, but narrow hard.** Don't try to do all 12 archetypes. Pick the two that
  share one deep skill:
  - `CAUSE_OF_SOURCE` — "which development most directly *led to* this source?"
  - `EFFECT_OF_SOURCE` — "this source most immediately *led to*…?"
  Both boil down to: *map a dated source to the single outside development that is
  date-consistent and specifically correct, then surround it with era-plausible
  traps.* Confidence the tuned model would beat the prompted base: **~91%**,
  conditional on grounding + a verifier.
- **Explicitly cut** the archetypes that sound impressive but have **no way to
  auto-check the answer** (competing-interpretation / evidence items), and the one
  that's **too easy** (a plain prompt already passes it). No point training those.
- **Solved the legal/sourcing question first** (`docs/05_data_sourcing_and_legal.md`).
  There's no existing dataset we're allowed to use — College Board's terms forbid AI
  training. So the plan: **distill from a frontier teacher model**, grounded on
  **public-domain primary sources** (published ≤1930, plus federal works & court
  opinions) and open textbooks. No College Board content ever enters the pipeline.
- **Planning went through a review loop.** A first plan (`plan_v1`) was sent to a
  validator, which came back **REVISE (major)** with 4 critical + 7 major holes.
  `plan_v2` fixed all 12 and was **approved**. That approved plan is what we've been
  executing.

**Net result of this phase:** a precise, falsifiable target ("one valid JSON MCQ
where the key needs an outside dated development and the 3 distractors are named,
era-plausible traps") and a legally clean data strategy — *before* writing any
training code.

---

## 2. Litmus testing (the build-gate) — the part that failed first

Before spending money generating data, we built an **eval harness** (`eval/`) to
answer one question: *can a frontier teacher even write these questions well, and is
the base small model actually bad at it?* If the teacher can't, there are no clean
labels and the whole project is dead. This is the "litmus test."

Setup: 10 held-out sources × 6 items × 3 runs. **Teacher = Claude Opus 4.8**,
**candidate = local Qwen3‑4B (Ollama)**, **judge = GPT‑5.5** (deliberately a
different model family so it doesn't grade its own work).

### Run 1 — FAILED (verdict: RETHINK)

| Model | Expert-grade | key_valid |
| :--- | ---: | ---: |
| Qwen3‑4B (candidate) | 13% | 43% |
| Claude Opus (teacher) | **28%** | 98% |

The rule says teacher below 50% = "no clean labels" = don't build. On its face,
this killed the project.

**But we dug into *why* it failed** (`docs/02b_litmus_results.md`). The teacher's
keys were almost always correct (98% valid) and the questions needed real outside
knowledge. The **single** thing dragging the score down: **distractor quality**.
On 67% of items, the wrong answers were **giveaways** — e.g. a "Social Darwinism"
option on a 1776 question, which any student eliminates in one second because it's
from the wrong century. 126 of 180 teacher items had a valid key and passed every
programmatic check but failed *only* on distractor subtlety.

This was actually the whole thesis confirmed: **writing tempting wrong answers is
the hard part**, and even a frontier model defaults to on-the-nose ones. The judge
was right to punish it; the litmus was doing its job.

### What we changed between Run 1 and Run 2

1. **Tightened the distractor rule in the prompt.** `wrong_era` traps must now come
   from a *neighboring, plausibly-confusable* era — never a century off. At most
   **one** distractor may be `wrong_era`; the other two must be same-era traps so
   the question can't be solved by chronology alone. Added a hard self-test: *"Could
   a prepared student eliminate this in under a second? If so, rewrite it closer."*
2. **Added a "repair" pass** (`eval/repair.py`): after generating an item, the model
   rewrites its own distractors to meet the stricter bar.
3. **Added a "near-miss" door.** We caught (via calibration, see §3) that the strict
   `spec_adherence==2` score the judge agreed with humans only ~40% of the time — it
   was too subjective to use as a hard gate. So the real decision metric became
   **near-miss rate** = passes every gate except that one subjective polish point.
4. **Parallelized the harness** (concurrent generation + judging) so a full run
   dropped from ~50 min to ~20 min.

### Run 2 — PASSED (verdict: BUILD / distill)

| Model | Near-miss | Expert-grade | key_valid |
| :--- | ---: | ---: | ---: |
| Qwen3‑4B (candidate) | 37% | 32% | 54% |
| Claude Opus (teacher) | **81%** | 80% | **84%** |

This is exactly the target regime: **teacher can (≥70%), prompted small can't
(≤55%)** — the gap that fine-tuning is supposed to close. Green light to generate
data.

---

## 3. Golden set + calibration

Before trusting the automated judge/verifier to filter thousands of generated items,
we had to prove those automated graders actually agree with a human.

- **Built a 30-item gold set** (`data/gold/gold.jsonl`), hand-graded by a human on
  four dimensions: key historically correct, key uniquely best, distractors
  era-plausible, and spec adherence.
- **Calibration tooling** (`eval/calibrate.py`) exports a *blind* sample (judge's
  verdicts hidden), lets a human grade it, then scores judge-vs-human agreement with
  Cohen's kappa.
- **What calibration told us:** the judge is reliable on the things that matter
  (key validity), but on the subjective `spec_adherence` polish score it agreed with
  humans only ~40% (negative kappa). **That's why we demoted it from a hard gate to
  a secondary quality score** and made near-miss the decision metric. This is a case
  of the measurement tool being corrected by the calibration, not the model.
- **Also hardened the corpus itself.** A corpus-integrity audit (`eval/audit_corpus.py`)
  catches sources whose text doesn't match their attribution (e.g. a "Reagan 1983"
  entry that a Wikisource search actually resolved to a modern speech). It flagged
  and we **dropped 4 mis-fetched stimuli**
  (`adams_inaugural_1797`, `dubois_talented_tenth_1903`, `jfk_cuban_missile_1962`,
  `reagan_evil_empire_1983`).

---

## 4. The dataset (the actual deliverable)

With the gate passed and graders calibrated, we grew the corpus and ran the factory.

**Corpus growth:** the seed corpus went from 14 → **86 public-domain primary
sources** (`data/build_seed_corpus.py` fetches from Wikisource / federal archives /
open textbooks, with a provenance manifest). The date-tagged **developments table**
(used both to ground correct answers and to catch anachronisms) grew from 84 → **167**
entries. Sources are split with a **contamination firewall**: the sources used to
generate training data are *disjoint* from the litmus and eval sources.

**The generation factory** (`eval/generate.py`) runs a hands-off loop per
(source, archetype):

```
generate (teacher) → repair distractors → Stage A programmatic checks
  → Stage B judge (near-miss) → Stage C key-verifier (independent solve, 3 votes)
  → keep only survivors, loop until target hit
```

No per-item human grading — the calibrated graders do the filtering.

### Final dataset stats (`data/generated/`)

| Metric | Value |
| :--- | :--- |
| **Kept items** | **816** (audited) |
| Balance | 408 `CAUSE_OF_SOURCE` / 408 `EFFECT_OF_SOURCE` (perfectly even) |
| Distinct source stimuli | 68 (12 items each) |
| Periods covered | all of 2–9 (spread: 12 / 60 / 144 / 84 / 108 / 228 / 132 / 48) |
| Distractor traps used | `partially_true` 881, `true_but_irrelevant` 875, `wrong_era` 527, `scope_mismatch` 161 |
| Went through repair pass | 815 / 816 |
| Generation time | ~9,830 s (~2.7 hrs) |

Two files ship: `train.jsonl` (clean items + provenance/judge/verify metadata) and
`train_sft.jsonl` (the same items formatted as system+user+assistant chat triples
for training). Formatting is done by `train/format_dataset.py`.

---

## 5. Training details (what's set up, ready to run)

Notebook: `train/qlora_qwen3_4b.ipynb` — a Colab (free **T4** GPU is enough) QLoRA
fine-tune via **Unsloth**.

| Setting | Value |
| :--- | :--- |
| Base model | `unsloth/Qwen3-4B` (4-bit) — same as the local candidate |
| Method | QLoRA (LoRA rank `r=16`, alpha 32, dropout 0, all attn+MLP projections) |
| Max sequence length | 4096 (prompt ~2.1k tok + JSON completion fits) |
| Loss | **response-only** — the prompt is masked, so the model is scored *only* on the JSON it should produce |
| Batch | 2 × grad-accum 8 = effective 16 |
| Epochs / steps | 2 epochs (~78 optimizer steps on the 629-item strict-clean set) |
| LR / scheduler | 2e‑4, cosine, 5 warmup steps, adamw_8bit, weight decay 0.01 |
| Resilience | checkpoints every 20 steps to Google Drive → survives a Colab disconnect and auto-resumes |
| Mask check | notebook decodes non-`-100` label tokens before training and asserts they are assistant JSON |

The plan after training: export to GGUF, register the tuned model in Ollama as a
second candidate, grow the held-out eval set to ~25–30 disjoint sources, and run the
**base-vs-tuned** comparison on the harness. The win condition is **tuned near-miss
rate > base**, with the base-vs-tuned gap the whole project is built to demonstrate.

### Notebook cleanup postmortem — failed sync attempt (July 9, 2026)

After the training notebook was built, we did a cleanup pass before treating it as
the v2 training artifact. The request was to edit the notebook if anything was
unoptimized or stale, and to rename anything that should become v2.

**What failed:** there were two copies of the notebook:

- repo copy: `train/qlora_qwen3_4b.ipynb`
- loose copy: `/Users/rohanpalivela/Documents/qlora_qwen3_4b.ipynb`

The loose `/Documents` copy had one real footgun: the `torchao` fallback install was
uncommented, so a normal Run All would upgrade `torchao` even when the fallback was
not needed. The repo copy had the safer version, but still needed a v2 naming pass
and some cleanup. Codex successfully updated the repo copy, but failed to overwrite
the loose `/Documents` copy because that path is outside the workspace write root and
the app's approval reviewer returned a 403 before the outside-workspace write could
run.

**Impact:** the source-of-truth notebook in the repo is now cleaned up, but the loose
copy in `/Documents` may still be stale. Anyone launching the loose notebook could
still hit the unnecessary `torchao` upgrade unless that file is manually replaced or
the outside write is explicitly approved later.

**What changed in the repo notebook:**

- renamed the run to `qwen3-4b-apush-v2` via a single `RUN_NAME`
- derived checkpoint folders, adapter folders, GGUF folders, Drive paths, and
  Hugging Face repo names from that run name
- left the `torchao` repair as a commented fallback instead of an unconditional
  install
- added a CUDA guard, cleaner dataset mapping, explicit `packing=False`, and
  bf16/fp16 selection
- made checkpoint auto-resume parsing stricter (`checkpoint-<int>` directories only)
- fixed the sanity-generation cell so it uses `eval.prompt_loader.LitmusPrompt`
  instead of reading the project prompt and then ignoring it
- cleared stale outputs and execution counts so the notebook opens as a fresh v2 run

**Verification:** the edited repo notebook is valid JSON, has 13 cells, has zero
stored outputs/execution counts, and all code cells parse after notebook magics are
stripped. The notebook was not executed end-to-end because that requires a Colab GPU
runtime and network installs.

**Follow-up:** keep `train/qlora_qwen3_4b.ipynb` as the canonical notebook. If a
working copy is needed in `/Documents`, copy it from the repo after approving that
outside-workspace write, or open the repo notebook directly in Colab.

### Training-data audit postmortem — why the first tuned model may have been weak

After the first tuned model looked poor, we audited the supposedly "passed" JSONL
again with stricter SFT-specific checks. The judge had scored item quality, but it
did not catch every way the **training target** could contradict the prompt.

**Major findings:** first, every SFT completion omitted
`requires_outside_knowledge`, even though the system prompt's output schema requires
it. That means the model saw a prompt demanding one schema and a target JSON object
missing one field. For a small 4B model, that kind of repeated schema contradiction
is enough to produce brittle or incomplete JSON at inference.

Second, the answer-position distribution was badly collapsed: the raw generated set
had 807 `A` keys, 9 `B` keys, and zero `C`/`D` keys. The judge/verifier can bless
individual items while missing this dataset-level tell. A fine-tune on that artifact
would learn "put the answer first" far more strongly than it learns robust APUSH
question construction.

**Other issues found:**

- 33 records embedded option labels directly in option text (`A. ...`, `B. ...`),
  creating inconsistent target formatting.
- 4 records had incomplete `trap_types`; their labels were inferred from rationale
  prefixes before final audit.
- 2 records had `trap_types` lists that contradicted the rationale prefixes; the
  rationale prefixes were treated as source of truth.
- 187 total records were quarantined under strict v2 rules. This includes clear
  cause/effect direction contradictions, weak trap-diversity rows, one row with two
  `WRONG_ERA` traps, and same-year/contemporaneous `EFFECT_OF_SOURCE` rows that
  need regeneration or human review before training.

**Fix added:** `train/audit_dataset.py` now builds a strict-clean split:

- `data/generated/train_clean.jsonl` — 629 repaired/validated, answer-balanced records
- `data/generated/train_sft_clean.jsonl` — SFT chat triples for training
- `data/generated/train_quarantine.jsonl` — 187 records held out for regeneration or
  human review
- `data/generated/train_audit_report.json` — reproducible counts/examples

The QLoRA notebook now trains from `train_sft_clean.jsonl`. The original
`train.jsonl` / `train_sft.jsonl` files remain as the historical generated set, but
they should not be treated as the canonical v2 training input.

**Still-open process risks:** the generated data still follows the litmus/free-recall
prompt rather than the fuller candidate-development contract in `prompts/data_gen_prompt.md`;
the original bulk generation used the same model family for judge and verifier; and
the exact base model identity should be pinned across training, Ollama base eval, and
GGUF export before claiming a clean base-vs-tuned comparison.

---

## 6. Where we are right now

- ✅ Research, taxonomy, feasibility, legal sourcing, approved plan
- ✅ Litmus gate: failed Run 1, diagnosed, fixed the prompt, **passed Run 2 (BUILD)**
- ✅ Gold set + calibration (which corrected our own scoring)
- ✅ Corpus grown, 4 bad sources dropped, **816-item dataset generated**
- ✅ Training notebook built and configured
- ✅ SFT data re-audited; **629-record answer-balanced strict-clean training set** produced
- ⏳ **Next:** run the fine-tune, then the base-vs-tuned eval

> _Training results + base-vs-tuned comparison will be appended below once the run
> completes._
