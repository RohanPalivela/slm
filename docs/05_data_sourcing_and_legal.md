# Data Sourcing & Legal Analysis — Deliverable 5

> The user has **no pre-existing question dataset**. Per the spec, training data
> is **distilled from a frontier teacher model**, but every question must hang on
> a **stimulus**, and those stimuli must be **legally reusable**. This document is
> the legal analysis of *what we may source and how*, the resulting **seed
> corpus** ([`../data/`](../data/)), and the reproducible **scraper**
> ([`../data/build_seed_corpus.py`](../data/build_seed_corpus.py)).
>
> *Not legal advice — an engineering summary of publicly documented licenses/terms
> for briefing counsel. Every claim is cited.* Full source-by-source detail was
> produced by a research subagent; the load-bearing conclusions are below.

---

## 0. The strategy in one paragraph

Ground everything on **public-domain primary sources** (U.S. works published
**≤1930**, plus U.S. federal works and court opinions, which are uncopyrightable
at any age) and **openly-licensed textbook prose**; **generate** the questions
synthetically from that corpus with a teacher model; use **MMLU
`high_school_us_history` (MIT)** *only* as a held-out eval; and keep **all College
Board material out of the data pipeline**, deriving only a hand-written taxonomy
from their public framework.

---

## 1. Two cross-cutting facts that shape the whole strategy

1. **OpenStax *U.S. History* is now CC BY-NC-SA 4.0, not CC BY 4.0.** The current
   edition (site, help center, and the GitHub `LICENSE`) is
   **Attribution-NonCommercial-ShareAlike**. The legacy 2014/2015 editions were
   **CC BY 4.0** and — because CC licenses are irrevocable — a genuinely
   CC-BY-notice-bearing archived copy remains usable under CC BY 4.0. **Practical
   consequence:** if the model may ever be commercial, current OpenStax's "NC"
   is a live problem and "SA" imposes copyleft. Prefer **The American Yawp
   (CC BY-SA 4.0)** for commercial-friendly grounding, or a verified legacy CC BY
   OpenStax copy, or request commercial permission from OpenStax.
2. **The public-domain foundation is the safe path, and the cutoff is ≤1930.** As
   of **2026-01-01**, U.S. works published in **1930 or earlier** are public
   domain (95-year term; 1931 joins in 2027). Separately, **U.S. federal
   government works have no copyright**, and **judicial opinions/statutes are
   uncopyrightable** (government-edicts doctrine, *Georgia v. Public.Resource.Org*,
   2020). *(This corrects the informal "pre-1929" heuristic; the corpus labels use
   "published ≤1930".)*

---

## 2. Recommended legal sourcing stack

| Source | License / rights | Role in the seed corpus | Key restriction / caveat |
| :--- | :--- | :--- | :--- |
| **Wikisource** (PD works) | Public domain (US) | Primary sources: speeches, laws, treaties, platforms, opinions | Verify each work is ≤1930 or federal/edict; *editorial notes* are CC BY-SA |
| **Project Gutenberg** | Underlying texts PD | Book-length PD prose | **Strip the PG header/footer/license and the "Project Gutenberg" mark**; use mirrors |
| **LoC / Chronicling America** | PD (≤1930) / federal | Period newspaper text; cartoon context | loc.gov JSON API (no key, rate-limit); filter to ≤1930 |
| **National Archives / DocsTeach** | Federal works = PD (per-item labeled) | Founding & government documents | Skip items labeled "In Copyright"; NARA won't confirm status |
| **Yale Avalon Project** | PD by age | Treaties, statutes, founding docs | Add acknowledgment; rely on underlying PD status |
| **CourtListener / Caselaw Access** | PD (government-edicts) | SCOTUS/landmark opinions as stimuli | Bulk data + API available |
| **The American Yawp** | **CC BY-SA 4.0** | **Commercial-OK** secondary/textbook prose + Primary Source Reader | **ShareAlike** obligations; attribute |
| **OpenStax *U.S. History* (legacy)** | **CC BY 4.0** (archived copy) | Textbook prose (commercial-OK) | Keep a dated copy proving the CC BY notice |
| **OpenStax *U.S. History* (current)** | **CC BY-NC-SA 4.0** | Textbook prose (non-commercial only) | **NC blocks commercial use**; SA copyleft; or request permission |
| **MMLU `high_school_us_history`** | **MIT** (wrapper) | **Held-out EVALUATION only** (~204 test items) | Benchmark → don't train on it; some items may carry 3rd-party rights |
| **LoC P&P cartoons** (Puck/Judge/Harper's) | PD (≤1930) / "no known restrictions" | Cartoon **text descriptions** as stimuli | Author your own description; keep repro number + date |
| **Gilder Lehrman** | Revocable license; paid permission | Reference only | ❌ Not for corpus/training |
| **College Board CED / FRQs / MCQs** | © College Board; **AI-training prohibited** | ❌ **Exclude from pipeline** | Terms forbid reproduction, scraping, data-mining, AI training |

---

## 3. College Board materials — the hard "exclude" line

College Board's terms explicitly prohibit reproduction, scraping, data-mining, and
**training any AI system** on their content. Using their released questions as
**training data** would be both likely copyright infringement of expressive works
**and** a contractual violation; AI-training fair-use law is contested. Therefore:

- **Training pipeline:** **zero** College Board content. Ever.
- **Taxonomy/design:** derived by hand from the **public course framework**
  (skills, reasoning processes, periods, themes). The CED **sample MCQ stems** were
  used for commentary and analysis only (a textbook fair-use purpose — transformative, no market
  substitution), are clearly labeled "(analysis only, not training data)," and are
  **never ingested** into the dataset.
- **Eval:** if an APUSH-flavored external check is wanted, use MMLU
  `high_school_us_history` (MIT) as a held-out set — **not** College Board items.

---

## 4. Two risks to flag before scaling

1. **ShareAlike collision.** Do **not** blend **CC BY-SA** (American Yawp,
   Wikisource editorial notes) with **CC BY-NC-SA** (current OpenStax) inside one
   derivative — the copyleft terms conflict. Keep sources **segregated with
   per-chunk provenance** so licensing can be proven and curated later. The seed
   corpus records `license` + `source_url` + `provenance` on **every** item for
   exactly this reason.
2. **Teacher-model Terms of Service is a separate gate.** Corpus licensing is
   independent of the **teacher model's ToS**. Several frontier providers restrict
   using their **outputs to train another model**. **Before distilling, confirm
   the chosen teacher's terms permit generating training data for this SLM.** This
   is a precondition in the training plan (Deliverable 4), not an afterthought.

---

## 5. The seed corpus we built ([`../data/`](../data/))

| File | What it is | Legal basis |
| :--- | :--- | :--- |
| [`seed_stimuli.jsonl`](../data/seed_stimuli.jsonl) | 14 stimuli: 11 public-domain primary sources (Declaration, Federalist 10, Monroe Doctrine, Seneca Falls, Douglass 1852, Omaha Platform, Carnegie, Beveridge, + federal works FDR 1933 / Truman 1947 / Brown 1954) and 3 **synthetic** secondary-source arguments (project-authored) for the F5 crown-jewel archetypes | PD (≤1930 or federal) + original composition |
| [`apush_periods_themes.json`](../data/apush_periods_themes.json) | 9 periods × 8 themes content vocabulary | Facts from CED framework (not expressive text) |
| [`apush_key_developments.json`](../data/apush_key_developments.json) | 167 date-tagged developments (expanded from 84 after validator C4), tagged `kind` (mechanism / background / event) so a specific-vs-background `scope_mismatch` pair exists per episode; the **anachronism verifier** table + distractor pool + keyable-answer grounding set | Historical facts (uncopyrightable); dates to be re-verified against OpenStax/Yawp at scale |
| [`build_seed_corpus.py`](../data/build_seed_corpus.py) | Reproducible pipeline: validate corpus, fetch PD sources from Wikisource, print OpenStax/Yawp/eval pointers, write provenance manifest | — |
| [`corpus_manifest.json`](../data/corpus_manifest.json) | Machine-readable provenance + exclusion policy + risk flags | — |

**The scraper was run and verified:** `--fetch-wikisource` successfully pulled
full public-domain text for the Declaration of Independence, Declaration of
Sentiments, Douglass's 1852 speech, the Gettysburg Address, the Omaha Platform,
and "The March of the Flag" (a few Wikisource page-titles 404 and are handled
gracefully; the hand-curated `seed_stimuli.jsonl` is the source of truth). The
fetch cache is git-ignored (reproducible, not canonical).

> **Why 14 seed stimuli is enough for now.** This stage proves the *legal
> pipeline* and seeds the litmus run. The full training corpus is built downstream
> by (a) scaling PD primary-source ingestion via `build_seed_corpus.py`, (b)
> pulling CC-BY(-SA) textbook prose for note-seeds, and (c) generating questions on
> top with the teacher model — all within the license constraints above.

---

## 6. Coverage vs the v1 archetypes

| Archetype family | Seed coverage | Gap to close before bulk gen |
| :--- | :--- | :--- |
| F1/F2 (comprehension, sourcing, contextualization) | Strong (all 11 primary sources support these) | — |
| F3/F4 (causation, CCOT, comparison) | Strong (date-tagged developments table enables the anachronism-verified items) | Extend developments table beyond 84 for full period coverage |
| F5 (argument & evidence, crown jewel) | 3 synthetic secondary sources | Add ~10 hand-verified secondary-source arguments (PD historiography or project-authored) before F5 bulk gen |

Full sources list and citation keys: [`sources.md`](sources.md).
