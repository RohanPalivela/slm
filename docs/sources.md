# Research Sources

Sources consulted for the MCAT question taxonomy (Deliverable 1). AAMC is the
primary authority; psychometric guidance grounds the "what makes a good
question" section; test-prep sources corroborate the surface-form taxonomy.

## Primary — AAMC (official)

- **Scientific Inquiry and Reasoning Skills** (SIRS 1–4 with worked examples per
  section) — https://students-residents.aamc.org/media/9061/download
- **What's on the MCAT Exam?** (full content outline: 10 Foundational Concepts,
  Content Categories, per-section SIRS distribution 35/45/10/10, discipline
  percentages) — https://students-residents.aamc.org/media/9261/download
- **Scientific Inquiry & Reasoning Skills: Overview** —
  https://students-residents.aamc.org/whats-mcat-exam/scientific-inquiry-reasoning-skills-overview
- **CARS Section: Overview** (3 skills; 30/30/40 weighting) —
  https://students-residents.aamc.org/whats-mcat-exam/critical-analysis-and-reasoning-skills-section-overview
- **CARS Section: Passage Types** —
  https://students-residents.aamc.org/critical-analysis-and-reasoning-skills/critical-analysis-and-reasoning-skills-section-passage-types

## Section structure & surface-form taxonomy (test prep, corroborating)

- Kaplan — *What's Tested on the MCAT* (section counts; passage vs discrete) —
  https://www.kaptest.com/study/mcat/whats-tested-on-the-mcat-2/
- Kaplan — *What's Tested on the MCAT: CARS* (CARS sub-types: Main Idea, Detail,
  Inference, Definition-in-Context, Function, Strengthen–Weaken, Apply) —
  https://www.kaptest.com/study/mcat/whats-tested-on-the-mcat-cars/
- MedSchoolCoach — *The 4 MCAT Sections* —
  https://www.medschoolcoach.com/mcat-sections/
- King of the Curve — *Top 5 MCAT Question Types* and *Passage Approach*
  (data interpretation, experimental design, application, Roman-numeral) —
  https://kingofthecurve.org/blog/mcat-question-types-strategies
- schoolbag.info — *General Chemistry Strategy for the MCAT* (three science
  passage types; Roman-numeral & EXCEPT/LEAST/NOT strategy) —
  https://schoolbag.info/chemistry/mcat_general_2015/2.html
- JackWestin — *CARS Strategy (2026)* and *CARS Passage Mapping* —
  https://jackwestin.com/blog/mcat-cars-strategy-2026/

## Item-writing / distractor quality (psychometric authority)

- **Medical Council of Canada** — *Multiple-choice question guidelines*
  (homogeneous options; plausible distractors from misconceptions; no
  all/none-of-the-above) — https://mcc.ca/wp-content/uploads/Multiple-choice-question-guidelines.pdf
- **NBME** guidance as summarized in: *The Art and Science of Item Writing: A
  Review of Established Guidelines for Multiple Choice Questions* —
  https://files.eric.ed.gov/fulltext/EJ1494236.pdf
- *Assessment of distractor functionality in MCQs* (functional distractor = one
  chosen by >=5% of students; need >=3 functional distractors) —
  https://journals.lww.com/mjdy/fulltext/2026/02000/assessment_of_distractor_functionality_in_multiple.4.aspx
- *The Importance of Writing Effective Distractors* (Haladyna & Rodriguez;
  distractors from novice errors via think-aloud) —
  https://theelearningcoach.com/elearning_design/tests/the-importance-of-writing-effective-distractors/

## In-repo assets (see `prev_data/`)

- `speedrun_question_bank.json.gz` — 1,586 MCQs (169 OpenMCAT w/ passages &
  per-choice explanations; 1,417 MMLU MCAT-relevant). Legally reusable
  (AGPL-3.0 / MIT) per `prev_data/build_question_bank.py` header.
- `speedrun_concepts.json` — 60-concept content taxonomy across 7 topics.
- `speedrun_first_principles.json` — hand-authored first-principle cards.
- `speedrun_paraphrase.json` — 30 cards × 2 reworded transfer items.

## SLM feasibility evidence

Sources consulted for the SLM feasibility assessment (Deliverable 3,
`docs/03_feasibility_assessment.md`). These ground the claims about what
fine-tuned small models (0.6B–4B, QLoRA + distillation) can and cannot do
reliably, and the size/scope decision.

### Pro — fine-tuned small models win at narrow, structured tasks

- **LoRA Land: 310 Fine-tuned LLMs that Rival GPT-4** (Zhao et al., 2024) —
  arXiv:2405.00732 — https://arxiv.org/abs/2405.00732 . 310 QLoRA fine-tunes
  across 10 base models (≤8B) and 31 tasks; 4-bit LoRA beats base by ~34 pts and
  GPT-4 by ~10 pts on average (best fine-tune 0.756 vs GPT-4 0.661). *Caveat:*
  GPT-4 still wins 6/31 on broad/complex tasks (Python, MMLU); fine-tune wins are
  concentrated in narrow, classification-oriented tasks. Models are 7B, tasks are
  mostly classification (directional support, not proof, for ≤4B generative
  quality).
- **Knowledge Distillation with Structured Chain-of-Thought for Text-to-SQL**
  (Thaker & Bresler, 2025) — arXiv:2512.17053 —
  https://arxiv.org/abs/2512.17053 . Distilling a *structured* formal blueprint
  into an SLM (via QLoRA) beats unstructured-CoT distillation by +8.1 pts,
  chiefly by cutting syntactic/schema errors — the direct analogue for the
  closed-set distractor-schema argument.
- **Mitigating Hallucination in SLMs via Contrastive Chain-of-Thought
  Fine-Tuning** (Baker & Al-Qrize, 2025) — Zenodo,
  https://doi.org/10.5281/zenodo.18538736 . Pairing correct reasoning with
  explicitly labeled logical fallacies (LoRA on Phi-2) reduces hallucination and
  improves final-answer accuracy by +12.5% vs standard fine-tuning — supports
  "distractor = named error" training and the DPO/negatives stretch rung.
- **KD-LoRA: A Hybrid Approach to Efficient Fine-Tuning with LoRA and Knowledge
  Distillation** (2024) — arXiv:2410.20777 — https://arxiv.org/abs/2410.20777 .
  Establishes LoRA+KD as a standard efficient recipe (with the JKU "KdQLoRA"
  thesis, https://epub.jku.at/obvulihs/download/pdf/11767041 , corroborating QLoRA+KD).

### Counter-evidence — sub-4B weaknesses (the risks to design around)

- **How Large Language Models Perform Arithmetic Reasoning in 2025** — OpenReview,
  https://openreview.net/pdf?id=MYEr4iPFMn . Measures the exact Qwen3 family:
  Qwen3-0.6B collapses to 1.4% accuracy in direct-answer mode (vs 85.8%
  step-by-step) due to format-compliance failure, while Qwen3-4B/8B are robust
  (96%+) across modes and 4B≈8B (0.5-pt gap). Direct basis for the documented
  **0.6B→4B reliability threshold** and the 4B size pick.
- **EasyMath: A 0-shot Math Benchmark for SLMs** (2025) — arXiv:2505.14852 —
  https://arxiv.org/abs/2505.14852 . SLMs fail multi-digit/large-number
  arithmetic and GSM-Symbolic-style perturbations; "direct distillation of
  complex reasoning often fails to benefit them… they perform better with
  shorter, simpler chains." Basis for excluding `QUANTITATIVE_APPLICATION` and
  capping reasoning at ~2 hops.
- **State of the Art and Future Directions of Small Language Models: A Systematic
  Review** (MDPI, 2025) — https://www.mdpi.com/2504-2289/9/7/189 . ~1/5 of SLM
  failures are factual/consistency hallucinations ("plausible-sounding
  fabrications" from lean embedding spaces); but MobileLLM-350M matches
  Llama-2-7B on narrow API-call tasks. Basis for treating single-best-answer
  factual correctness (SC5) as the crux, and narrow scope as the mitigation.
- **Test-Time Scaling for Multistep Reasoning in SLMs via Search** (2025) —
  https://openreview.net/pdf/32d6610b7d8a0cd1f7fa9546333922a6e978073c.pdf .
  Confirms SLM multi-step reasoning compounds early errors and is hallucination-
  prone; motivates decomposition/verification passes over single forward passes.
