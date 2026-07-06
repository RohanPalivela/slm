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
