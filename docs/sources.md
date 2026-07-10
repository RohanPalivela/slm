# Research Sources

Sources for the APUSH question taxonomy (Deliverable 1) and the SLM feasibility
assessment (Deliverable 3). The College Board Course and Exam Description (CED)
is the primary authority; prep-source corpora corroborate the distractor-trap and
command-phrase taxonomy; the feasibility evidence grounds what fine-tuned small
models can/cannot do reliably.

## Primary — College Board (official)

- **[CED-*] AP U.S. History Course and Exam Description** (the core framework:
  6 historical thinking skills, 3 reasoning processes with sub-aspects, 9 periods
  with exam weighting, 8 themes, and a full **Sample Exam Questions** section with
  official stimulus-based MCQs) —
  https://apstudents.collegeboard.org/sites/default/files/2019-05/ap-us-history-course-and-exam-description.pdf
  - `[CED-skills]` Historical Thinking Skills (Developments and Processes; Sourcing
    and Situation; Claims and Evidence in Sources; Contextualization; Making
    Connections; Argumentation).
  - `[CED-reasoning]` Reasoning Processes (Comparison §1.i–iii; Causation §2.i–v;
    Continuity and Change §3.i–iii).
  - `[CED-content]` Nine periods (1491–present) with per-unit exam weighting
    (Units 1 & 9: 4–6% / 6–8%; core Units 3–8: 10–17% each) and eight themes
    (NAT, WXT, GEO, MIG, PCE, WOR, ARC, SOC).
  - `[CED-sample]` Sample Exam Questions — official stimulus-based MCQ sets
    (Declaratory Act 1766; Erie Canal / Larson; Republican platform 1860; 1940s
    Boeing image; Ford 1974) used in this repo for **taxonomy analysis only**, not
    as training data.
- **[CED-exam] AP United States History — Exam page** (section structure, timing,
  weights; "questions usually appear in sets of 3–4"; primary/secondary sources,
  images, graphs, maps; SAQ/DBQ/LEQ specifics) —
  https://apcentral.collegeboard.org/courses/ap-united-states-history/exam
- **AP U.S. History Course page** (six historical thinking skills summary; eight
  themes; nine units) —
  https://apcentral.collegeboard.org/courses/ap-united-states-history
- **[sg] AP U.S. History Scoring Guidelines (2025)** (DBQ/LEQ rubrics: thesis,
  contextualization, evidence, sourcing, complexity) —
  https://apcentral.collegeboard.org/media/pdf/ap25-sg-us-history-set-1.pdf

## MCQ design, distractor architecture & command phrases (prep corpora, corroborating)

- **[missed-mcq] "APUSH Most Missed MCQ Topics: 8 Trap Clusters, Wrong Answer
  Logic"** — the four distractor traps (wrong-era, historically-true-but-wrong,
  scope-mismatch, partially-true), the "most directly" specific-vs-background
  distinction, and worked eliminations —
  https://www.apushistoryexamprep.com/ap-us-history-most-missed-mcq-topics.html
- **[reasoning-guide] "AP U.S. History Historical Thinking Skills"** (command
  phrase → skill mapping; "read the prompt as a skill signal") —
  https://www.apushistoryexamprep.com/ap-us-history-historical-thinking-skills.html
- **RevisionDojo — APUSH MCQ approach / exam format 2025** (sets of 2–4 on a
  stimulus; predict-then-eliminate; wrong-era elimination) —
  https://www.revisiondojo.com/blog/how-to-approach-apush-multiple-choice-questions-proven-2025-guide
  and https://www.revisiondojo.com/blog/the-apush-exam-format-explained-complete-2025-guide
- **UWorld — APUSH exam format** (section table; "many questions include
  historical sources; interpret and connect") —
  https://collegeprep.uworld.com/ap/ap-us-history/exam-format-and-information/
- **APUSH source-analysis guide** (primary vs secondary; POV/audience/purpose;
  "understand the source AND connect to outside knowledge") —
  https://www.apushistoryexamprep.com/ap-us-history-primary-vs-secondary-sources.html
- **Perfection Learning / Barron's** (reasoning processes; themes; core periods
  ~80%) — https://perfectionlearning.com/nextstep/historical-thinking-skills ;
  https://www.barronseduc.com/blogs/ap/post/how-to-study-for-ap-us-history-exam

## Data sourcing & legality

See [`05_data_sourcing_and_legal.md`](05_data_sourcing_and_legal.md) for the full,
citation-backed legal analysis (OpenStax CC BY, public-domain primary-source
repositories, College Board copyright/fair-use, and open MCQ datasets).

## SLM feasibility evidence (Deliverable 3)

These ground the claims about what fine-tuned small models (0.6B–4B, QLoRA +
distillation) can and cannot do reliably, and the size/scope decision. They are
domain-general SLM findings (not APUSH-specific) and are the same evidence base a
reliability-first, distillation-based fine-tuning project should reason from.

### Pro — fine-tuned small models win at narrow, structured tasks

- **[loraland] LoRA Land: 310 Fine-tuned LLMs that Rival GPT-4** (Zhao et al.,
  2024) — arXiv:2405.00732 — https://arxiv.org/abs/2405.00732 . QLoRA fine-tunes
  (≤8B) beat base by ~34 pts and GPT-4 by ~10 pts on average, concentrated in
  **narrow, classification-oriented** tasks. *Caveat:* wins are 7B/classification,
  so treat as directional support for "narrow + tuned wins," not proof for ≤4B
  generative quality.
- **[struct-sql] Knowledge Distillation with Structured Chain-of-Thought**
  (2025) — arXiv:2512.17053 — https://arxiv.org/abs/2512.17053 . Distilling a
  *structured blueprint* beats unstructured-CoT distillation by +8.1 pts, chiefly
  by cutting schema errors — the analogue for the closed distractor-trap schema.
- **[ccot] Mitigating Hallucination in SLMs via Contrastive CoT Fine-Tuning**
  (2025) — Zenodo, https://doi.org/10.5281/zenodo.18538736 . Pairing correct
  reasoning with **explicitly labeled fallacies** (LoRA on Phi-2) reduces
  hallucination and improves accuracy by +12.5% — supports "distractor = named
  trap" training and the DPO/negatives stretch.
- **[kd-lora] KD-LoRA** (2024) — arXiv:2410.20777 — https://arxiv.org/abs/2410.20777
  . LoRA + knowledge distillation as a standard efficient recipe.

### Fact-density crux — history is long-tail and small models fabricate it

- **[mallen] When Not to Trust Language Models** (Mallen et al., ACL 2023;
  PopQA) — https://arxiv.org/abs/2212.10511 . LM memorization is limited to
  *popular* facts; scaling barely helps the long tail; retrieval (non-parametric
  memory) complements parametric memory. Grounds the APUSH fact-density crux and
  the table-grounding lever (select the outside development, don't free-recall it).
- **[slm-util] Can Small Language Models Use What They Retrieve?** (2025) —
  even with *oracle* retrieval, ≤7B models often fail to extract the answer on
  facts they don't already know (7B ≈ 14.6%); standard instruction-tuning is
  insufficient for grounding, but RAFT-style fine-tuning fixes utilization. The
  honest downward pressure on the feasibility confidence, and why grounding must
  be *trained in*.
- **[drag] DRAG: Distilling RAG into SLMs** (ACL 2025, arXiv:2506.01954) —
  https://arxiv.org/abs/2506.01954 . Distilling RAG (evidence + graph grounding)
  into SLMs cuts hallucination and raises factual accuracy. Supports the
  distillation-plus-grounding recipe as the SLM-appropriate path to factual
  reliability.

### Counter-evidence — sub-4B weaknesses (the risks to design around)

- **[arith-2025] How LLMs Perform Arithmetic Reasoning in 2025** — OpenReview,
  https://openreview.net/pdf?id=MYEr4iPFMn . Qwen3-0.6B collapses to 1.4% in
  direct-answer mode (format-compliance failure) vs 85.8% step-by-step, while
  Qwen3-4B/8B are robust (96%+) and 4B≈8B. Basis for the **0.6B→4B reliability
  cliff** and the 4B size pick.
- **[slm-review] State of the Art … Small Language Models: A Systematic Review**
  (MDPI, 2025) — https://www.mdpi.com/2504-2289/9/7/189 . ~1/5 of SLM failures are
  **factual/consistency hallucinations** ("plausible-sounding fabrications"); but
  MobileLLM-350M matches Llama-2-7B on narrow tasks. Basis for treating
  single-best-answer **factual correctness as the crux** (acute for a fact-dense
  domain like history) and narrow scope + grounding as the mitigation.
- **[easymath] EasyMath: A 0-shot Math Benchmark for SLMs** (2025) —
  arXiv:2505.14852 — https://arxiv.org/abs/2505.14852 . SLMs fail multi-step
  numeric reasoning; "direct distillation of complex reasoning often fails… better
  with shorter, simpler chains." Basis for capping reasoning at ~2 hops and
  avoiding multi-step numeric stimuli.

### Long-tail recall & grounding (Deliverable 3 — supplementary web research)

These three ground the two load-bearing APUSH-specific claims: that a fact-dense domain
stresses small-model factual recall (the SC-KEY crux) and that **grounding the
answer to the date-tagged developments table** is the decisive mitigation.

- **[mallen] Mallen et al., "When Not to Trust Language Models: Investigating
  Effectiveness of Parametric and Non-Parametric Memories"** (ACL 2023) —
  https://aclanthology.org/2023.acl-long.546.pdf . Introduces PopQA; shows LM
  memorization is limited to **popular** facts and **scaling barely helps the long
  tail**, while retrieval (non-parametric memory) complements parametric memory
  (Adaptive Retrieval). *Grounds:* the SC-KEY crux (APUSH is long-tail-heavy) and
  the table-grounding lever. *Caveat:* open-domain QA on GPT-Neo/OPT/GPT-3, not
  ≤4B MCQ authoring.
- **[slm-util] "Can Small Language Models Use What They Retrieve? An Empirical
  Study of Retrieval Utilization Across Model Scale"** (2025) —
  arXiv:2603.11513 — https://www.arxiv.org/pdf/2603.11513 . Even with **oracle**
  retrieval, models ≤7B fail to extract the answer 85–100% of the time on unknown
  facts (7B: **14.6%**); standard instruction-tuning is insufficient for grounding
  at small scale, but **RAFT-style fine-tuning fixes utilization**. *Grounds:* the
  honest downward pressure on the confidence (why 91%, not 95%), the need to
  *train in* grounding, and the candidate-set fallback. *Caveat:* open-domain QA
  with instruction-tuned baselines; our task is more constrained.
- **[drag] "DRAG: Distilling RAG for SLMs from LLMs… via Evidence and
  Graph-based Distillation"** (ACL 2025) — arXiv:2506.01954 —
  https://arxiv.org/abs/2506.01954 . Distilling RAG (evidence/graph grounding)
  into SLMs cuts hallucination and raises factual accuracy (>MiniRAG by up to
  27.7%). *Grounds:* the distillation + grounding recipe as the SLM-appropriate
  path to factual reliability. *Caveat:* QA/knowledge tasks, not MCQ authoring.

> **Citation key convention:** bracketed keys (e.g. `[CED-sample]`, `[missed-mcq]`,
> `[loraland]`) are retained here as project references.
