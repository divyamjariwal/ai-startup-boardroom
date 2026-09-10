# Startup Boardroom — Project Blueprint & Session Handoff

This file is the **single source of truth** for project progress. It is written so a fresh
session (with no memory of prior chats) can continue the work. Read it top to bottom before
touching code.

## 0. Resume in a new session — do this first

1. **Read this whole file.** §1–§8 = product + prior steps (V1, Steps 1–3). §9 = Step 4
   (Historical Reference Class), which is the active work. §9F = locked decisions. Then the
   `OPEN DECISIONS / KNOWN LIMITATIONS` and §10 constraints.
2. **Confirm the baseline**: from the repo root run
   `python -m unittest discover -s tests` → expect **337 tests, all passing**.
   (Windows; the venv is Python 3.13 even though `runtime.txt` says 3.11 — that's fine.
   No ruff/mypy/black installed — the test suite is the quality gate. `py_compile` for syntax.)
3. **Git state**: Step 4 engines (4A–4E) are committed and pushed — commit `64eb274`
   `feat: add Step 4 historical reference-class pipeline (4A-4E)` on `main`. Integration + QA
   are not started. Commit/push only when the user asks.
4. **Env**: `.env` has `GROQ_API_KEY` (used by `agents/base_agent.py`). There is **no**
   `TAVILY_API_KEY`, so `services.research.configured_provider()` returns `None` locally →
   reference-class discovery returns status `UNAVAILABLE_NO_PROVIDER` and every test injects a
   fake provider + stub extractor (no live internet, no live Groq).
5. **The next task is Integration** — see `## NEXT SESSION — START HERE` (inside §9). Step-4
   *engine* work (4A–4E) is COMPLETE and regression-protected; do not redesign it.
6. **Working style for this project** (from §8/§10): lightweight, deterministic Python; prefer
   it over another LLM call; no new DB/embeddings/vector store/framework; small, explainable,
   testable changes; keep existing tests green; update this file when a step completes.

Run the app: `streamlit run streamlit_app.py`. Run one test module:
`python -m unittest tests.test_reference_class_engine`.

## 1. Product thesis

An **assumption & evidence engine for early-stage startup ideas**. The product does not hand
down a verdict; it exposes the load-bearing assumptions behind an idea, marks which are
externally supported vs. unverified, shows which ones the decision hinges on, and points the
founder at what to validate next. Scores are decision-support signal, not investment advice.

## 2. Current architecture

```
Idea
 → ResearchEngine (optional Tavily) → EvidenceStore (in-memory, per run)
 → 4 specialist agents (Investor / CTO / Marketing / Product), each given a filtered evidence package
     → self-reported claims       → verify_claim() → VerifiedClaim{status, importance, supports_metric}
     → self-reported AssumptionDraft{impact, uncertainty, supports_metric, claim_ids}
 → deterministic scoring (evidence-adjusted) → boardroom score → investment band
 → AssumptionEngine (deterministic): dedupe → criticality → rank → evidence_status → RankedAssumption
 → SensitivityEngine (deterministic): decision-critical assumptions → failure scenarios → SensitivityResult
 → ValidationEngine (deterministic): ranked assumptions → category templates → ValidationPlan
 → Debate agent + Chairperson/Summary agent (narrative only)
 → Streamlit UI (tabs incl. Assumptions, Sensitivity, Validation Plan, radar charts)
   + PDF report (incl. assumptions, sensitivity, validation sections)
```

Stack: Python 3.11, Streamlit, Groq API, Pydantic v2 (strict), Plotly, ReportLab.

## 3. Completed V1 features

- Six LLM roles: Investor, CTO, Marketing, Product, Debate moderator, Chairperson/Summary.
- Strict Pydantic schemas for every agent output.
- Deterministic 0–100 scoring per agent + averaged boardroom score with investment bands.
- Optional external research (Tavily) → typed `Evidence` with hostname-based source classification.
- Per-run `EvidenceStore`; agent claims verified against it (`verify_claim`).
- Executive dashboard, per-agent radar charts, Debate + Verdict tabs, Evidence & Sources tab, PDF export.

## 4. Step 1 completed — evidence influences scores

- **Evidence-aware scoring**: verified claims can *discount* a specialist score, never raise it.
  Wired into the existing `calculate_*_score` functions; no new orchestration.
- **`supports_metric`**: one optional field on `ClaimDraft` (`^[a-z_]+_score$` or `None`). A claim
  tagged with one of that agent's metric names discounts only that metric; untagged/non-matching
  claims discount all of the agent's metrics. Nothing is discarded.
- **Verifier safety fixes** (so a status can be trusted by the scorer):
  - Unresolvable cited evidence IDs can no longer yield `SUPPORTED`.
  - `UNKNOWN` source-quality weight lowered to ≤ `LOW`.
  - A detected contradiction yields `CONTRADICTED` even if weak supporting evidence also exists.
  - `SUPPORTED` requires at least one cited source of `MEDIUM`+ quality.
- Tests in `tests/test_models_and_scoring.py` (12, all pass).

## 5. Step 2 completed — Assumption Engine

- **Structured `AssumptionDraft`** (`models/assumption.py`): replaces the old free-text
  `AgentResult.assumptions: list[str]`. Fields: `id` (`^A-[A-Z]+-\d{3}$`), `text`, `category`,
  `impact` 1–5, `uncertainty` 1–5, optional `supports_metric`, `claim_ids` (default empty).
  Specialist prompts now emit 3–5 assumptions each, phrased as necessary conditions.
- **Deterministic `AssumptionEngine`** (`services/assumption_engine.py`):
  `rank_assumptions(agent_results, verified_claims) -> list[RankedAssumption]`. No LLM, no
  embeddings, no fuzzy matching.
- **Exact deduplication**: normalize text (lowercase, trim, collapse whitespace); exact matches
  collapse into one — first id/text/category kept, **max** impact, **max** uncertainty, union of
  `claim_ids`, first-occurrence order preserved.
- **Criticality** = `impact × uncertainty` (1–25), computed deterministically.
- **Decision-critical threshold = 16** (`DECISION_CRITICAL_THRESHOLD`). Sort order:
  criticality desc → impact desc → uncertainty desc → original position; ranks assigned after sort.
- **Evidence status** linked through `claim_ids` against the already-verified claims (verifier not
  modified; confidence/coverage not used). Precedence:
  `CONTRADICTED > SUPPORTED > PARTIALLY_SUPPORTED > UNCERTAIN`; no resolvable linked claim →
  `UNVERIFIED`.
- **Integration**: `Assumptions` tab in `streamlit_app.py` (rank, text, category, impact,
  uncertainty, criticality, evidence status; decision-critical highlighted) and a concise
  "Key Assumptions" section in `services/pdf_generator.py`.
- Tests in `tests/test_assumption_engine.py` (21, all pass). Scoring is unchanged by Step 2.

## 5b. Step 3 completed — Sensitivity Analysis + Founder Validation Plan

Two new deterministic engines consume the existing `RankedAssumption` objects. No LLM
call, no new dependency; `services/verifier.py` and `services/scoring.py` are untouched;
Step-1 scoring behaviour and all thresholds are unchanged.

**Sensitivity Engine** (`models/sensitivity.py`, `services/sensitivity_engine.py`):
`run_sensitivity(investor, cto, marketing, product, current_boardroom_score, current_band,
ranked_assumptions) -> SensitivityResult`. One **failure scenario** per decision-critical
assumption (criticality ≥ 16). Decision-support, not prediction — no probabilities.
- Fixed penalty model: `scenario_penalty = 0.20 * (impact/5) * (uncertainty/5)`, applied
  only in the "assumption failed" world.
- Ownership: the ranked assumption's normalized text is matched against each original
  `AgentResult.assumptions` (reuses `assumption_engine._normalize`); a merged assumption
  can own multiple specialists and is applied to each independently.
- `supports_metric` present **and** a metric of an owning specialist → **MAPPED_METRIC**:
  the original raw metric is read from the `AgentResult`, reduced to
  `metric * (1 - scenario_penalty)`, and that specialist's score is recomputed with the
  existing aggregation rule (`scoring._evidence_adjusted_score`, so evidence adjustment
  still applies).
- `supports_metric` absent → **MAPPED_SPECIALIST**: `scenario_specialist_score =
  current_specialist_score * (1 - scenario_penalty)`.
- `supports_metric` names a metric no owning specialist has, or no owner is found →
  **UNMAPPED**: no scenario score, no `score_delta` (explicit gap over fake precision).
- Hypothetical boardroom score = mean of the four hypothetical specialist scores, rounded
  (mirrors `calculate_boardroom_score`); band via the existing `get_investment_decision`.
  Scores clamped to 0–100. Stored scores/`AgentResult`s are never mutated.
- `SensitivityScenario` carries `assumption_id/text`, impact, uncertainty, criticality,
  `decision_critical`, `mapping_status`, `affected_specialists`, `affected_metric`,
  `scenario_penalty`, current/scenario boardroom score, `score_delta`, current/scenario
  band, `band_changed`, and a human-readable `note` ("If this assumption proves false…").

**Validation Engine** (`models/validation.py`, `services/validation_engine.py`):
`build_validation_plan(ranked_assumptions) -> ValidationPlan`. One `ValidationItem` per
ranked assumption, input order preserved.
- Priority ladder (named constants): criticality ≥ 20 `VERY_HIGH`, ≥ 16 `HIGH`, ≥ 12
  `MEDIUM`, else `LOW` — so every decision-critical assumption is at least `HIGH`.
- Method / success signal / recommended sample from deterministic **category-keyword
  templates**: customer|market → discovery interviews; pricing → willingness-to-pay;
  acquisition → landing-page experiment; retention → cohort pilot; technology|scalability
  → prototype/load test; product → usability test; business_model → pricing experiment;
  unknown → customer-discovery fallback. Sample sizes are named constants
  (`SAMPLE_INTERVIEWS=10`, `SAMPLE_ACQUISITION=50`, `SAMPLE_TECH_PROTOTYPE=1`, …).
- `test_question = "Can we verify that: <assumption>?"` (no NLP). `rationale` templated
  from criticality + evidence status + decision-critical flag.

**UI** (`streamlit_app.py`): two new tabs — **📉 Sensitivity** (current score, per-assumption
failure-scenario score, delta, `current band → scenario band`, band-changing rows
highlighted, "Scenario analysis — not a prediction.") and **🧪 Validation Plan** (ranked
action list: priority, evidence status, method, test question, success signal, sample,
rationale). Dashboard otherwise unchanged.

**PDF** (`services/pdf_generator.py`): two new optional trailing params
(`sensitivity_result`, `validation_plan`) and two new sections after "Key Assumptions" —
"Sensitivity Analysis" (labelled *hypothetical failure scenarios, not predictions*) and
"Founder Validation Plan". Existing callers unaffected.

- Tests: `tests/test_sensitivity_engine.py` (10) + `tests/test_validation_engine.py` (16).
  Full suite **59 tests, all pass** (33 pre-existing + 26 new). Boardroom scoring
  unchanged by Step 3.

## 6. Current scoring rule

```
status penalty:  SUPPORTED 0.00 · PARTIALLY_SUPPORTED 0.10 · UNCERTAIN 0.15 · UNSUPPORTED 0.25 · CONTRADICTED 0.40
per claim:       penalty = status_penalty × (importance / 5)
per metric:      total_penalty = agent-level penalties + penalties tagged to that metric
                 multiplier    = clamp(1 − total_penalty, 0.5, 1.0)
                 adjusted      = raw_metric(1–10) × 10 × multiplier
agent score:     mean of adjusted metrics, rounded to 2 dp
```

No claims ⇒ multiplier 1.0 ⇒ identical to the pre-Step-1 result. `confidence` and
`evidence_coverage()` are deliberately not used for scoring. Assumptions do not affect the score.

## 7. Known limitation

The verifier is still **lexical / token-overlap** matching with a small negation blocklist. It has
no semantic understanding: paraphrased contradictions and numeric misstatements can still pass as
support. Assumption evidence status inherits this limitation, since it reads verified-claim
statuses. NLI/semantic verification is deferred.

The sensitivity penalty model is a deliberately simple, transparent rule
(`0.20 * severity * uncertainty_factor`), not a calibrated forecast. Scenarios are hypothetical
"what if this fails" illustrations, never predictions or probabilities. An assumption that cannot
be tied to a specific metric or specialist is reported as `UNMAPPED` rather than assigned a
fabricated delta.

## 8. Design constraints (keep these)

- Lightweight architecture; no major refactors.
- Deterministic Python logic wherever possible; prefer it over another LLM call.
- Avoid unnecessary new agents, databases, embeddings, external APIs, dependencies, or frameworks.
- Keep changes small, explainable, and testable.
- **Historical startup evidence** (discover similar past startups, analyze their outcomes, blend
  with current market evidence) is a planned *core* future feature — design choices should not
  block it.

## 9. Step 4 — Historical Startup Discovery / Reference Class (engines COMPLETE; Integration + QA remain)

Discover real past/current startups similar to the founder's idea, describe what happened to
them, and surface recurring patterns — a **descriptive** evidence layer, never predictive, kept
**independent** of specialist scoring and the assumption engine for now.

### Project status

```text
4A — COMPLETE
4B — COMPLETE
4C — COMPLETE
4D — COMPLETE
4E — COMPLETE
Integration — NEXT
End-to-end QA — NOT STARTED
```

Full test suite: **337 tests, all passing** (`python -m unittest discover -s tests`).
= 59 pre-Step-4 + 118 for 4A (`test_reference_class_models.py` 77, `test_idea_profile.py` 41)
+ 69 for 4B (`test_similarity.py`) + 31 for 4C (`test_reference_discovery.py`)
+ 34 for 4D (`test_reference_outcomes.py`) + 26 for 4E (`test_reference_class_engine.py`).

The whole Step-4 pipeline now exists end to end:

```
build_idea_profile(text)                     -> IdeaProfile            (4A, services/idea_profile.py)
discover_reference_class(idea)                -> DiscoveryResult        (4C, services/reference_discovery.py)
verify_outcomes(discovery)                    -> OutcomeVerificationResult (4D, services/reference_outcomes.py)
build_reference_class(verification)           -> ReferenceClass         (4E, services/reference_class_engine.py)
```

(4B `score_similarity` / `is_relevant` is called inside 4C.)

### Step-4 file inventory (committed in `64eb274`)

**New source files**

| File | Role | Key public API |
|---|---|---|
| `models/reference_class.py` | all Step-4 Pydantic models + constants + `build_summary_narrative`, `_reject_forbidden` | `IdeaProfile`, `CandidateProfile`, `SimilarityBreakdown`, `VerifiedCandidate`, `ComparableStartup`, `DroppedCandidate`, `OutcomeAssessment`, `OutcomeSignal`, `ReferenceClass`, `ReferenceClassSummary`, `ReferenceClassPattern`, enums, `SIMILARITY_*`, `PATTERN_*`, `POLARITY_BY_OUTCOME`, `FORBIDDEN_DESCRIPTIVE_PHRASES` |
| `services/similarity.py` (4B) | deterministic idea↔candidate similarity | `score_similarity(idea, candidate)`, `is_relevant(breakdown)` |
| `services/reference_discovery.py` (4C) | search + 1 LLM extraction → scored candidates | `discover_reference_class(idea, *, provider=None, extractor=None) -> DiscoveryResult`; `discovery_queries`, `extract_candidates` |
| `services/reference_outcomes.py` (4D) | deterministic outcome classification | `classify_outcome(evidence) -> OutcomeAssessment`; `verify_outcomes(discovery) -> OutcomeVerificationResult` |
| `services/reference_class_engine.py` (4E) | aggregate → final artifact | `build_reference_class(verification) -> ReferenceClass` |
| `prompts/reference_class_extraction.txt` | the single 4C LLM prompt | — |

**Modified existing files** (all additive, no behaviour change to prior features)

| File | Change |
|---|---|
| `services/idea_profile.py` | 4A engine `build_idea_profile`; + `tokenize()` (4B); + `GEO_REGION_LABELS` (4C) |
| `STARTUP_BOARDROOM_CONTEXT.md` | this doc |

`services/research.py`, `services/scoring.py`, `services/verifier.py`, `streamlit_app.py`,
`services/pdf_generator.py`, and every pre-Step-4 model/agent are **untouched** so far.

**Test files** (run offline; fake provider + stub extractor, no live internet/Groq)

| File | Count |
|---|---|
| `tests/test_reference_class_models.py` (4A models) | 77 |
| `tests/test_idea_profile.py` (4A parser) | 41 |
| `tests/test_similarity.py` (4B) | 69 |
| `tests/test_reference_discovery.py` (4C) | 31 |
| `tests/test_reference_outcomes.py` (4D) | 34 |
| `tests/test_reference_class_engine.py` (4E) | 26 |
| pre-Step-4 (`test_models_and_scoring`, `test_assumption_engine`, `test_sensitivity_engine`, `test_validation_engine`) | 59 |
| **total** | **337** |

Shared test helpers `_FakeProvider`, `_relevant_candidate`, `_result`, `_stub` live in
`tests/test_reference_discovery.py` and are imported by the 4D/4E test files.

---

## NEXT SESSION — START HERE

The next task is **Integration** — wire the Step-4 pipeline into the app, and nothing more of the
engine work. Do not redo or redesign 4A–4E.

Start by reading:
1. this Markdown document (esp. §9A–§9E and §9F "Important architectural decisions")
2. streamlit_app.py  (the current orchestration + tabs; where `ResearchEngine`, the specialists,
   `AssumptionEngine`, `SensitivityEngine`, `ValidationEngine`, and the PDF are wired)
3. services/pdf_generator.py  (Step-3 added optional trailing params — same pattern to follow)
4. services/reference_discovery.py, services/reference_outcomes.py, services/reference_class_engine.py
5. models/reference_class.py  (`ReferenceClass` is the artifact the UI/PDF render)

Integration scope (keep it small, mirror the Step-3 wiring style):
- In `streamlit_app.py`, after the idea is entered: `profile = build_idea_profile(idea)` then
  `reference_class = build_reference_class(verify_outcomes(discover_reference_class(profile)))`.
  Cache it in `st.session_state` like `research_run`. It runs independently of specialist scoring
  and the assumption engine (design Decisions 2 & 3 — **do not** feed it into scoring/assumptions).
- Add ONE read-only tab (e.g. "📚 Reference Class"): status/message, the summary counts +
  `narrative` + `disclaimer`, the `patterns` (id, type, confidence, text), and the ranked
  `comparables` (name, similarity total, `outcome.outcome` + `outcome_year` + `outcome.rationale`,
  `matched_dimensions`, evidence links via `evidence_store.get(id).source_url`), plus a
  "candidates excluded" line from `dropped_candidates`.
- Add optional trailing params to `services/pdf_generator.py::generate_pdf` (default `None`) for a
  "Reference Class" section — existing callers unaffected (exact Step-3 pattern).
- No new dependency. `TAVILY_API_KEY` unset ⇒ the tab shows `UNAVAILABLE_NO_PROVIDER` and the
  rest of the boardroom is untouched.
- Then End-to-end QA.

---

### 9A. 4A completed — data layer + deterministic idea parsing

Files: `models/reference_class.py`, `services/idea_profile.py`,
`tests/test_reference_class_models.py`, `tests/test_idea_profile.py`.

- **`IdeaProfile`** (`models/reference_class.py`): coarse structured reading of a raw idea.
  Fields `raw_text`, `customer_type`, `customer_descriptor`, `problem`, `product_form`,
  `business_model`, `industry`, `geography`, `keywords` (≤20, regex-constrained, unique),
  `unresolved_fields`. Strict Pydantic, `extra="forbid"`.
- **`UnresolvedField`** enum (7 members) + `UNRESOLVED_FIELD_ORDER` (canonical order, shared by
  the builder and the validator).
- **Deterministic idea parsing**: `services/idea_profile.py::build_idea_profile(idea_text)
  -> IdeaProfile`. Pure, no I/O/LLM/randomness, byte-identical output for identical input.
  Ordered keyword maps + a few regexes; **coarse by design** (no synonymy beyond listed surface
  forms, no negation handling).
- **Sentinel / unresolved-field consistency**: three `mode="after"` validators — (1) `keywords`
  unique; (2) `unresolved_fields` unique **and** in canonical order; (3) **biconditional**: a
  field holds its sentinel (`"unspecified"` / `*.UNKNOWN`) **iff** its `UnresolvedField` is in
  `unresolved_fields`.
- **Keyword generation**: content tokens = length 3–40, not a pitch stop word, not a digit →
  top-10 unigrams by `(count desc, first-index asc)` + up to 4 bigrams; merged, ordered by
  first occurrence, capped at 12, unique, each matching `^[a-z0-9][a-z0-9.+\-]*( [a-z0-9]...)?$`.
- **Position-preserving bigrams**: two content tokens form a bigram **only** when adjacent in the
  *original* token stream (`pos+1`) — never merely adjacent after stop-word removal. A bigram is
  kept only if it introduces ≥1 token not already among the selected unigrams.
- **Evidence architecture**: the reference class uses its **own** per-run `EvidenceStore`
  instance (separate from the market `research_run.store`). The `E-###` evidence-id format is
  **unchanged**. `ReferenceClass` validators enforce traceability invariants **#2** (every
  `ComparableStartup.evidence_ids` entry resolves in the reference store) and **#4** (every
  `DroppedCandidate.evidence_ids` entry resolves).
- **`source_urls` removal decision**: `source_urls` was **removed** from `VerifiedCandidate`,
  `ComparableStartup`, and `DroppedCandidate`. Traceability is `evidence_ids →
  EvidenceStore.get(id) → Evidence.source_url`. Cross-model invariant **#3** (source_urls match
  store) was dropped with it.
- **`ReferenceClass` model**: `idea_profile`, `status` (`ReferenceClassStatus`), `comparables`
  (≤ `MAX_COMPARABLES` = 8), `dropped_candidates`, `patterns` (≤ `MAX_PATTERNS` = 12),
  `summary`, `evidence_store`, `discovery_search_count` (≤4), `verification_search_count` (≤8),
  `llm_calls` (`ge=0`; the code comment says "invariant 0" but on a real run it is **1** — the
  4C extraction call — see §9F).
  Validators check summary/`by_outcome` consistency, invariants #2/#4/#5 (patterns cite only
  included comparables), unique pattern ids, and status consistency **only** for
  `UNAVAILABLE_NO_PROVIDER` / `UNAVAILABLE_NO_MATCHES`.
- **LOW-confidence pattern rule**: `PatternConfidence` is only `LOW` or `MEDIUM` (never higher);
  `MEDIUM` requires `support_count ≥ 3` (`PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT`);
  `PATTERN_MIN_SUPPORT = 2`. A `LOW` pattern's `text` must read as a bounded observation about
  the retrieved sample ("2 of the 6 retrieved comparables…"), never a population-level claim.
  `FORBIDDEN_DESCRIPTIVE_PHRASES` + `_reject_forbidden()` block predictive language in every
  human-readable field (`rationale`, `basis` kept clean too, `pattern.text`, `summary.narrative`).
- **`build_summary_narrative()`**: fixed neutral wording; the "candidates excluded" sentence is
  emitted only when `dropped_count > 0`.
- **Tests**: `tests/test_reference_class_models.py` (77), `tests/test_idea_profile.py` (41).

### 9B. 4B completed — similarity engine

Files: `services/similarity.py` (new), `tests/test_similarity.py` (new),
`models/reference_class.py` (+`CandidateProfile`, additive), `services/idea_profile.py`
(+`tokenize()`, additive; `_tok` now delegates — behaviour identical).

- **Purpose**: deterministic, transparent similarity between the founder's `IdeaProfile` and one
  candidate startup → a fully-validated 4A `SimilarityBreakdown`. Runs before discovery so 4C can
  rank candidates and apply the relevance cut-off.
- **`CandidateProfile`** (`models/reference_class.py`): the structured attributes of one
  candidate — `name`, `one_liner`, `industry="unspecified"`, `geography: str | None = None`,
  `business_model`/`product_form`/`customer_type` (`*.UNKNOWN` defaults),
  `customer_descriptor: str | None = None`. Strict, `extra="forbid"`, **no validators**. Field
  names/types are a **strict subset of `VerifiedCandidate`** so 4C builds a `VerifiedCandidate`
  from `CandidateProfile` + `SimilarityBreakdown`.
- **`score_similarity(idea: IdeaProfile, candidate: CandidateProfile) -> SimilarityBreakdown`**:
  pure & deterministic — no network, no LLM, no `EvidenceStore`, no mutation, no randomness.
- **`is_relevant(breakdown: SimilarityBreakdown) -> bool`** = `breakdown.total >=
  SIMILARITY_INCLUSION_THRESHOLD` (45). The **single** relevance definition; matches the 4A
  `VerifiedCandidate` validator (`is_relevant == similarity.total >= 45`).
- **Six dimensions** (in `SimilarityDimension` enum order): `PROBLEM`, `CUSTOMER`, `INDUSTRY`,
  `PRODUCT_FORM`, `BUSINESS_MODEL`, `GEOGRAPHY`.
- **Weights**: read from `models.reference_class.SIMILARITY_WEIGHTS`
  (0.25 / 0.20 / 0.20 / 0.15 / 0.15 / 0.05). Never duplicated.
- **Scoring rules** (band *values* from the approved A/B spec design §4):
  - INDUSTRY: exact tag `1.0` / sibling `0.5` / unrelated `0.0` / either unspecified `0.30`.
  - PRODUCT_FORM: exact `1.0` / adjacent `0.5` / mismatch `0.1` / either `UNKNOWN` `0.30`.
  - BUSINESS_MODEL: exact `1.0` / related `0.6` / mismatch `0.1` / either `UNKNOWN` `0.30`.
  - CUSTOMER: same `customer_type` **and** descriptor content-token overlap → `1.0`;
    same type only → `0.5`; different known types with exactly one `CONSUMER` → `0.0`
    (conflict); different known org types (no `CONSUMER`) → `0.30`; either `UNKNOWN` → `0.30`.
  - GEOGRAPHY: same region `1.0` / both `"Global"` `0.7` / either unspecified (incl. `None`)
    `0.5` / one `"Global"` vs a specific region `0.5` / two different regions `0.3`.
  - PROBLEM: `overlap = |idea_terms ∩ one_liner_terms| / |idea_terms|`, where `idea_terms` =
    keyword tokens ∪ `problem` content tokens (`problem` skipped when `"unspecified"`); bands
    `≥0.50→1.0`, `≥0.30→0.70`, `≥0.15→0.50`, `0<overlap<0.15→0.30`, `==0→0.10`,
    either side has no usable terms → `0.30`.
- **Policy tables introduced because the spec was silent** (named constants in
  `services/similarity.py`, NOT spec text):
  - `_INDUSTRY_SIBLINGS` (unordered tag pairs): `{fintech,insurtech}`, `{healthtech,biotech}`,
    `{devtools,data_ai}`, `{devtools,cybersecurity}`, `{data_ai,cybersecurity}`,
    `{ecommerce,logistics}`, `{logistics,mobility}`, `{media,social}`.
  - `_PRODUCT_FORM_ADJACENCY`: APP–SAAS, APP–PLATFORM, APP–CONTENT, SAAS–PLATFORM, SAAS–API,
    SAAS–SERVICE, API–PLATFORM, MARKETPLACE–PLATFORM.
  - `_BUSINESS_MODEL_RELATED`: SUBSCRIPTION–FREEMIUM, SUBSCRIPTION–LICENSING,
    TRANSACTIONAL–MARKETPLACE, ADVERTISING–FREEMIUM.
  - `PROBLEM_OVERLAP_BANDS` (+ zero / small / insufficient-text scores).
  - `GEOGRAPHY_GLOBAL_VS_REGION_SCORE = 0.50`.
  Every enum member / industry tag in these tables was verified against the live enums and
  `INDUSTRY_TAGS`, and is guarded by `PolicyTableTests`.
- **Aggregation rule**: per dimension `weighted_score = score * weight` stored **raw / unrounded**
  (the 4A `DimensionScore` validator uses `math.isclose`); the **only** rounding is
  `total = round(100 * sum(weighted_score))` — exactly what the 4A `SimilarityBreakdown`
  validator recomputes and enforces.
- **matched / divergent**: `matched_dimensions` = dims scoring `≥ SIMILARITY_MATCH_THRESHOLD`
  (0.60); `divergent_dimensions` = dims scoring `≤ SIMILARITY_DIVERGENT_THRESHOLD` (0.30); both
  in `SimilarityDimension` order (matches the 4A validator).
- **basis / rationale**: each `DimensionScore.basis` is one deterministic factual line
  (≤ 200 chars). `rationale` is templated (≤ 600 chars) and **deliberately omits the candidate
  name** so a real company name containing a `FORBIDDEN_DESCRIPTIVE_PHRASES` substring (e.g.
  "Guaranteed Rate") can never make `score_similarity` raise.
- **Shared tokeniser**: `services/idea_profile.py::tokenize(text) -> list[str]` (new, public);
  4A `_tok` delegates to it. 4A keyword extraction and 4B problem overlap now agree on tokens.
- **Determinism**: enum-ordered iteration, `frozenset` lookups, no set/dict ordering leaks into
  output. Repeated calls → identical `model_dump()`; inputs never mutated.
- **Tests**: `tests/test_similarity.py` (69) — every dimension, every band, both threshold
  boundaries, exact 45 / 44 relevance boundary, identical profiles (→ total 100), no-information
  inputs (→ total 31, not relevant), determinism, non-mutation, basis/rationale length,
  forbidden-language check, `CandidateProfile` validation + `extra="forbid"`, invalid inputs,
  policy-table integrity, `tokenize`.

### 9C. 4C completed — reference-class discovery engine

Files: `services/reference_discovery.py` (new), `prompts/reference_class_extraction.txt` (new),
`tests/test_reference_discovery.py` (new, 31 tests), `services/idea_profile.py`
(+`GEO_REGION_LABELS` public constant, additive; no behaviour change). **Nothing else touched** —
`services/research.py`, `ResearchEngine`, `models/reference_class.py`, and all 4A/4B tests are
unchanged.

- **Purpose**: `IdeaProfile` → a small set of real, evidence-backed comparable startups, each
  scored by the 4B engine. Deliberately minimal: **2 internet searches + 1 LLM call per idea.**
- **Public API** (`services/reference_discovery.py`):
  - `discover_reference_class(idea: IdeaProfile, *, provider: ResearchProvider | None = None,
    extractor: ExtractorFn | None = None) -> DiscoveryResult`. `provider`/`extractor` default to
    the real Tavily provider (`configured_provider()`) and the real Groq call; both are
    **injection seams for tests** (same pattern as `ResearchEngine(provider=None)`).
  - `discovery_queries(idea) -> list[str]` — deterministic, exactly `MAX_DISCOVERY_QUERIES` (2)
    non-empty, distinct queries built from `IdeaProfile` fields (customer/problem/keywords for Q1;
    industry + product_form + keywords for Q2; `raw_text` fallback for degenerate ideas).
  - `extract_candidates(idea, evidence: list[Evidence]) -> CandidateExtraction` — the **one**
    Groq call via `agents.base_agent.run_agent` + `prompts/reference_class_extraction.txt`.
- **`DiscoveryResult`** (lives in the 4C service module, mirroring `services.research.ResearchRun`;
  `ConfigDict(arbitrary_types_allowed=True, extra="forbid")`): `idea_profile`, `status`
  (reuses `ReferenceClassStatus`), `candidates: list[VerifiedCandidate]`,
  `dropped: list[DroppedCandidate]`, `evidence_store: EvidenceStore` (its own per-run instance),
  `search_count`, `llm_calls` (0 or 1), `message`. One validator:
  `UNAVAILABLE_NO_PROVIDER ⇒ empty candidates/dropped and zero searches/llm_calls`.
- **`CandidateExtraction` / `ExtractedCandidate`** — the raw LLM output contract, deliberately
  **lenient** (`extra="ignore"`, permissive defaults) so a stray LLM key never fails the run;
  the **strict gate is `CandidateProfile`** downstream.
- **Evidence is the source of truth**: every search result → `Evidence` (reuses
  `classify_source`, `EvidenceStore` URL-dedup, `E-###` ids); the LLM must cite the
  `evidence_id`s it used per startup; a candidate with **no resolvable cited evidence id** is
  dropped `NOT_VERIFIED_AS_COMPANY`. Kept candidates carry those ids on
  `VerifiedCandidate.evidence_ids` → `evidence_store.get(id)` → `Evidence.source_url` + verbatim
  `excerpt`. No per-candidate follow-up searches.
- **Deterministic after the 2 searches + 1 LLM call**: query generation, evidence storage/ids,
  id resolution, attribute normalisation (`_normalize_industry` → `INDUSTRY_TAGS` or
  `"unspecified"`; `_normalize_geography` → `GEO_REGION_LABELS` + small alias map or `None`;
  `_normalize_enum` → enum value or `*.UNKNOWN`), dedup (`_dedupe_key`: lowercase, whitespace-
  collapsed, legal-suffix-stripped), `score_similarity`, `is_relevant`, status.
- **Connection to 4B**: builds `CandidateProfile` from normalised attributes → `score_similarity(
  idea, profile)` → `is_relevant(breakdown)` → assembles `VerifiedCandidate(...,
  similarity=breakdown, evidence_ids=..., is_company_verified=True,
  is_relevant=<is_relevant result>)`. Relevant → `candidates`; below threshold →
  `DroppedCandidate(INSUFFICIENT_RELEVANCE)`; duplicate → `DroppedCandidate(DUPLICATE,
  merged_into=...)`.
- **Failure / missing-data handling**: no provider → `UNAVAILABLE_NO_PROVIDER`; 1 of 2 searches
  fails + candidates produced → `PARTIAL`; both fail / zero results / LLM found nothing /
  extractor raises (`except Exception` — never crashes the boardroom) → `UNAVAILABLE_NO_MATCHES`
  (evidence still retained, `llm_calls=1` when the call was attempted); missing attributes →
  sentinels (handled neutrally by 4B); missing `one_liner` → falls back to the first cited
  excerpt (≤200 chars), else dropped.
- **Caps** (named constants): `MAX_DISCOVERY_QUERIES=2`, `DISCOVERY_RESULTS_PER_QUERY=5`,
  `MAX_CANDIDATES=6`, `DISCOVERY_CATEGORY=ResearchCategory.COMPETITORS`.
- **Tests**: `tests/test_reference_discovery.py` (31) — query generation, no-provider, happy
  path + evidence traceability, relevance decision matches the 4B contract, irrelevant/duplicate/
  unverified drops, URL dedup, unknown-evidence-id filtering, one-query-fail → `PARTIAL`,
  all-fail / extractor-raises / empty-extraction → `UNAVAILABLE_NO_MATCHES`, attribute
  normalisation, off-vocabulary → sentinel, `founding_year` range, `DiscoveryResult` validator,
  lenient `CandidateExtraction`, `GEO_REGION_LABELS`, full-run determinism. Uses a fake
  `ResearchProvider` and a stub extractor — **no live internet, no live Groq**.

### 9D. 4D completed — deterministic outcome verification

Files: `services/reference_outcomes.py` (new), `tests/test_reference_outcomes.py` (new, 34
tests). **Nothing else touched.**

- **Purpose**: per discovered candidate, decide *what appears to have happened to it* —
  `ACTIVE` / `ACQUIRED` / `PUBLIC` / `SHUT_DOWN` / `PIVOTED` / `UNKNOWN` — **only** from signal
  phrases found in the retrieved evidence excerpts. Conservative, mirrors `services/verifier.py`.
- **Public API** (`services/reference_outcomes.py`):
  - `classify_outcome(evidence: list[Evidence]) -> OutcomeAssessment` — the atomic classifier.
  - `verify_outcomes(discovery: DiscoveryResult) -> OutcomeVerificationResult` — maps every
    `DiscoveryResult.candidate` → `ComparableStartup` (= `VerifiedCandidate` + `outcome`).
- **`OutcomeVerificationResult`** (in the 4D service module; mirrors `DiscoveryResult`):
  `idea_profile`, `status` (passthrough), `comparables: list[ComparableStartup]`,
  `dropped: list[DroppedCandidate]` (passthrough), `evidence_store` (passthrough), `message`.
  One validator: every `comparable.evidence_ids` **and** `comparable.outcome.supporting_evidence_ids`
  must resolve in `evidence_store` (traceability).
- **No LLM, no network, no mutation, no randomness.** Purely: lowercase substring signal
  phrases over `"<title>\n<excerpt>"`, quality-weighting via the reused public
  `services.verifier.QUALITY_WEIGHT`, and 4-digit year parsing within an 80-char window of the
  matched phrase (filtered to `EARLIEST_PLAUSIBLE_YEAR .. today+1`).
- **Decision order**: terminal signal (`ACQUIRED`/`PUBLIC`/`SHUT_DOWN`) > `PIVOTED` > `ACTIVE`.
  - A concrete outcome requires ≥1 **MEDIUM+ quality** source (`QUALITY_WEIGHT >= MEDIUM`).
    Terminal signals seen only in `LOW`/`UNKNOWN` sources → `UNKNOWN`.
  - Conflicting terminal outcomes → resolved to the **most recent by parsed year**; if that is
    ambiguous/undated → `UNKNOWN` with `conflicting = True`.
  - `ACTIVE` requires a dated signal `>= today.year - (ACTIVE_SIGNAL_RECENCY_MONTHS // 12)` from
    a MEDIUM+ source; an old/undated funding mention → `UNKNOWN`.
  - No qualifying signal (bare homepage / directory / social page) → `UNKNOWN`. **"Has a
    website" is never `ACTIVE`.**
- **`OutcomeAssessment` contents**: `polarity` from `POLARITY_BY_OUTCOME`; `supporting_evidence_ids`
  = the distinct evidence ids of the *winning* signals; `signals` = `OutcomeSignal` records for
  the winners (for `UNKNOWN`, all detected signals, `supporting_evidence_ids = []`);
  `outcome_year` = max winning year; `confidence` = `best_quality_weight ×
  source_count_factor × recency_factor × (0.6 if conflicting)`, clamped ≤ 0.95, and pinned to
  0.1 for `UNKNOWN` (≤ `OUTCOME_UNKNOWN_MAX_CONFIDENCE`); `rationale` always states source
  count + strongest quality + year, descriptive-only (`FORBIDDEN_DESCRIPTIVE_PHRASES`-safe).
- **`verify_outcomes` also derives `ComparableFlag`s** on each comparable (on top of any from
  4C): `CONFLICTING_OUTCOME` iff `outcome.conflicting`; `PIVOT` iff outcome is `PIVOTED`;
  `SINGLE_SOURCE` iff exactly one evidence id; `WEAK_SOURCES` iff every resolved evidence item
  is below MEDIUM. These satisfy the `ComparableStartup` biconditional validators.
- **Tests** (`tests/test_reference_outcomes.py`, 34): one per outcome band; old/undated ACTIVE →
  UNKNOWN; homepage / LinkedIn page → UNKNOWN; LOW-only terminal → UNKNOWN; empty evidence →
  UNKNOWN; terminal > pivot > active ordering; conflict resolved-by-year and unresolvable;
  multi-source confidence lift; confidence ceiling; future-year ignored; rationale content;
  determinism; and `verify_outcomes` over a **real 4C `DiscoveryResult`** (fake provider + stub
  extractor) covering flag derivation, passthrough of idea/status/evidence/dropped, and the
  `OutcomeVerificationResult` traceability validator.

### 9E. 4E completed — reference-class aggregation

Files: `services/reference_class_engine.py` (new), `tests/test_reference_class_engine.py` (new,
26 tests), `services/reference_outcomes.py` (+2 additive passthrough fields on
`OutcomeVerificationResult`, defaults 0 — existing 4D tests unaffected).

- **Purpose**: `OutcomeVerificationResult` (4D) → the final 4A `ReferenceClass`. Deterministic;
  no LLM, no network, no mutation.
- **Public API**: `build_reference_class(verification: OutcomeVerificationResult) -> ReferenceClass`.
- **Ordering**: `comparables` sorted by `(-similarity.total, -outcome.confidence,
  -len(evidence_ids), name)`.
- **Summary**: `by_outcome` = comparables grouped by `outcome.outcome` (non-zero entries);
  `continued/ended/unclear` via `POLARITY_BY_OUTCOME`; `narrative` from `build_summary_narrative`
  (unchanged 4A function). Satisfies the `ReferenceClassSummary` validators exactly.
- **Pattern derivation** (`_derive_patterns`, deterministic counting — no LLM), each pattern a
  bounded "N of the M retrieved comparables …" observation, `id` = `RCP-01..RCP-12`, capped at
  `MAX_PATTERNS`:
  - `OUTCOME_TENDENCY` — for `ACQUIRED` / `PUBLIC` / `ACTIVE` with ≥ `PATTERN_MIN_SUPPORT` (2).
  - `RECURRING_RISK` — for `SHUT_DOWN` (≥2), and separately for ≥2 comparables flagged
    `CONFLICTING_OUTCOME`.
  - `COMMON_PIVOT` — for `PIVOTED` (≥2).
  - `GTM_PATTERN` — the *dominant* value of `business_model` / `product_form` / `customer_type` /
    `industry` when it covers ≥2 **and a majority (≥50%)** of the comparables;
    `linked_assumption_hint` = `business_model` / `product_form` / `customer` / `market`.
  - `UNKNOWN` outcomes never produce an outcome pattern.
  - `confidence` = `MEDIUM` iff `support_count >= PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT` (3)
    **and** `support_count >= 50%` of comparables; else `LOW`. Text years via `_year_span`
    (`"(2019)"` / `"(2019-2021)"` / none).
- **ReferenceClass fields**: `status` / `idea_profile` / `dropped_candidates` / `evidence_store`
  are passthrough from 4D; `discovery_search_count = min(verification.search_count,
  MAX_DISCOVERY_QUERIES)`; `verification_search_count = 0` (this architecture runs no
  per-candidate verification searches); `llm_calls = verification.llm_calls` (**1** on a real
  run — the 4C extraction call; the old "Step-4 invariant 0" note on that field is superseded).
- **`OutcomeVerificationResult` gained** `search_count` / `llm_calls` (additive, default 0,
  populated by `verify_outcomes` from the `DiscoveryResult`) so 4E has one complete input object.
- **Tests** (`tests/test_reference_class_engine.py`, 26): run the real 4C→4D→4E chain with a fake
  provider + stub extractor. Cover passthrough, ordering + tie-break, summary counts + narrative,
  every pattern type + MEDIUM/LOW confidence + majority gate + year span + invariants (#5, unique
  ids, `FORBIDDEN_DESCRIPTIVE_PHRASES`), UNKNOWN → no pattern, `< 2` comparables → no pattern,
  all three `UNAVAILABLE_*` / `PARTIAL` statuses, an empty hand-built `OutcomeVerificationResult`,
  and determinism.

### 9F. Important architectural decisions (do NOT reverse)

- **`source_urls` was intentionally removed** from candidate/comparable/dropped models. Do not
  re-add. Traceability = `evidence_ids → EvidenceStore.get(id) → Evidence.source_url`.
- **Evidence traceability goes through a per-run reference `EvidenceStore`** (a separate instance
  from the market research store). `E-###` id format is retained.
- **`ReferenceClassStatus.PARTIAL` is an engine invariant, not a `ReferenceClass` model
  invariant** — ≥1 `ResearchProviderUnavailable` during the run. The model has no field for it
  and does not check it. Only `UNAVAILABLE_NO_PROVIDER` / `UNAVAILABLE_NO_MATCHES` are
  model-validated status cases.
- **4B (`services/similarity.py`) is pure and deterministic** — no network, no LLM, no
  `EvidenceStore` access, no mutation, no randomness. It does **not** perform research or
  discovery.
- **4B weights** come from `models.reference_class.SIMILARITY_WEIGHTS`; never duplicate the
  numbers. **Weighted scores are stored raw**; only `total` is rounded, via
  `round(100 * sum(weighted))`.
- **`is_relevant` / `SIMILARITY_INCLUSION_THRESHOLD` (45)** is the single relevance definition,
  kept consistent with the 4A `VerifiedCandidate` validator.
- **`CandidateProfile` is a strict field-name/type subset of `VerifiedCandidate`** — keep them
  in sync. 4C assembles a `VerifiedCandidate` from `CandidateProfile` + `SimilarityBreakdown`.
- **4C uses exactly one LLM call** (`extract_candidates` via `run_agent` +
  `prompts/reference_class_extraction.txt`) and **2 searches**. The LLM only *extracts* named
  startups + attributes *from retrieved evidence excerpts* and must cite `evidence_id`s; it never
  invents companies or facts. Do not add per-candidate searches, a heuristic-extraction
  framework, or a `CandidateExtractor` class hierarchy.
- **`DiscoveryResult` (4C output) is NOT a `ReferenceClass`.** It carries `list[VerifiedCandidate]`
  (no outcomes yet) + `list[DroppedCandidate]` + its own `EvidenceStore`. 4D turns those into
  `ComparableStartup`; 4E builds the `ReferenceClass`.
- **4C reuses `services.research`** (`ResearchProvider`, `configured_provider`, `classify_source`)
  and `EvidenceStore` unchanged — `ResearchEngine`/`research.py` were **not** modified.
- **`GEO_REGION_LABELS`** (public, in `services/idea_profile.py`, derived from `_GEO_REGIONS`) is
  the single source of truth for geography label normalisation. 4C normalises the LLM's
  geography string to one of these (or `None`) before scoring.
- **No success probabilities anywhere.** `PatternConfidence` never exceeds `MEDIUM`; `LOW`
  patterns are bounded observations about the retrieved sample. `FORBIDDEN_DESCRIPTIVE_PHRASES`
  guard is enforced by 4A model validators.
- **`IdeaProfile` sentinel ⇔ `unresolved_fields` membership is a hard biconditional.**
  `build_idea_profile` is coarse by design. The position-preserving bigram rule must not regress.
- **Historical evidence stays an independent layer.** It does **not** feed specialist scoring,
  the assumption engine, or the validation engine (design Decisions 2 & 3). Do not wire that
  integration during Integration/QA without explicit approval — the Reference Class tab is
  render-only.
- **4D (`services/reference_outcomes.py`) is deterministic and evidence-only** — no LLM, no
  network, no mutation. It never infers `ACTIVE` from a resolving domain / social page; a
  concrete outcome needs a signal phrase in a MEDIUM+ source. Terminal > pivot > active; conflicts
  resolve by most recent year else `UNKNOWN`+`conflicting`.
- **4E (`services/reference_class_engine.py`) is deterministic and counting-only** — no LLM.
  Patterns are bounded "N of M retrieved comparables …" observations; GTM patterns need a
  majority value; `MEDIUM` confidence needs ≥3 support **and** ≥50% coverage.
- **`ReferenceClass.llm_calls` is 1 on a real run** (the single 4C extraction call). The 4A code
  comment calling it a "Step-4 invariant: 0" predates the approved 4C LLM call and is stale —
  the field is `ge=0` and 4E sets it from `verification.llm_calls`. 4A's own tests use the
  default 0 and still pass.
- **Phase ownership**: 4C discovery — **DONE**. 4D outcome verification — **DONE**. 4E
  aggregation — **DONE** (`build_reference_class(OutcomeVerificationResult) -> ReferenceClass`).
  **NEXT = Integration**: wire `build_idea_profile → discover_reference_class → verify_outcomes →
  build_reference_class` into `streamlit_app.py` as an independent read-only tab + optional PDF
  section (Step-3 wiring style); it must **not** feed specialist scoring or the assumption engine.
- **Existing 4A–4E tests are regression-protected**: `tests/test_reference_class_models.py`,
  `tests/test_idea_profile.py`, `tests/test_similarity.py`, `tests/test_reference_discovery.py`,
  `tests/test_reference_outcomes.py`, `tests/test_reference_class_engine.py` must stay green and
  must not be rewritten during Integration.

## OPEN DECISIONS / KNOWN LIMITATIONS

- The `{devtools, data_ai, cybersecurity}` industry-sibling cluster (esp. the
  `data_ai`–`cybersecurity` pair) is the **softest** entry in `_INDUSTRY_SIBLINGS` and the most
  likely to need tuning. `_PRODUCT_FORM_ADJACENCY`, `_BUSINESS_MODEL_RELATED`, the PROBLEM
  overlap bands, and `GEOGRAPHY_GLOBAL_VS_REGION_SCORE = 0.50` are all **4B policy** (the A/B
  spec was silent) — tune via the named constants in `services/similarity.py`, not the spec.
- **GEOGRAPHY comparison is exact-string** on the `GEO_REGIONS` canonical label. 4C handles this
  via `_normalize_geography` (maps to `GEO_REGION_LABELS` + a small alias map, else `None`).
  Coverage is only as good as that alias map + the LLM honouring the enumerated labels in the
  prompt; an unrecognised region → `None` (neutral 0.5), never a wrong match.
- **4C design choice — one LLM call, done** (the earlier "deterministic `HeuristicCandidateExtractor`
  only" note is superseded): identifying real companies + attributes from messy web excerpts is
  exactly what an LLM does well and a heuristic framework does badly. `extract_candidates` is
  **one function + one prompt + one lenient Pydantic contract** — not a pluggable abstraction.
  A non-LLM fallback was deliberately not built.
- **4C recall is bounded by 2 searches × 5 results.** Genuinely novel ideas, or ideas whose
  `IdeaProfile` is mostly `unresolved`, will often yield `UNAVAILABLE_NO_MATCHES`. Tunable via
  `MAX_DISCOVERY_QUERIES` / `DISCOVERY_RESULTS_PER_QUERY` / `MAX_CANDIDATES` in
  `services/reference_discovery.py`.
- **4C `DiscoveryResult` has no cross-model traceability validator** (unlike 4A `ReferenceClass`
  invariants #2/#4). The engine guarantees every kept-candidate `evidence_id` resolves in
  `evidence_store` by construction; if 4E consumes `DiscoveryResult` it should still assert this
  when assembling the `ReferenceClass`.
- **4C attribute-level provenance is candidate-level**: a `VerifiedCandidate` cites the
  `evidence_id`s it was built from, and those `Evidence.excerpt`s are retained verbatim — but
  there is no per-field ("founded 2015" ↔ which sentence) mapping. Sufficient for a small
  reference class; revisit only if 4E/UI needs finer provenance.
- `build_idea_profile` coarseness: keyword maps only, no synonymy beyond listed surface forms,
  no negation handling; unusual or cross-domain ideas land many `unresolved_fields`. An optional
  LLM idea-profiling pass is a possible future upgrade — **not** part of Step 4.
- **4D outcome classification is lexical** (signal-phrase substrings + a phrase-adjacent year
  regex), the same class of limitation as `services/verifier.py`: paraphrased outcomes, negated
  phrasing ("was *not* acquired"), and years far from their phrase can be missed or misread. It
  errs toward `UNKNOWN`. The signal-phrase lists and the 80-char year window in
  `services/reference_outcomes.py` are the tuning surface. `FAILED` is intentionally folded into
  `SHUT_DOWN` (per the approved 4A taxonomy) — do not add a `FAILED` outcome.
- **4D `ACTIVE` recency** uses whole years (`today.year - ACTIVE_SIGNAL_RECENCY_MONTHS // 12`,
  i.e. ~2 calendar years), not exact month arithmetic — deliberately coarse.
- **4E patterns are shallow by design**: they count over `ComparableStartup` fields (outcome,
  flags, business_model / product_form / customer_type / industry). They cannot surface a
  *thematic* recurring risk ("kept losing to incumbents on distribution") because that would need
  an LLM over the excerpts — deferred. Tuning surface: `_PATTERN_MAJORITY`, the generator
  functions, and the phrase templates in `services/reference_class_engine.py`.
- **4E `verification_search_count` is always 0** (no per-candidate verification searches in this
  architecture). If a future step adds them, set this field and revisit `_derive_patterns`.
- Pre-existing (unrelated to Step 4): the claim verifier is still lexical / token-overlap (see
  §7); NLI/semantic verification remains deferred.

## 10. Design constraints (still apply — see also §8)

- Lightweight, deterministic, explainable, testable; prefer Python logic over another LLM call.
- No new database / embeddings / vector store / external API / framework for Step 4.
- Reuse the existing research + evidence + LLM infrastructure; do not add a curated corpus.
- 4D and 4E must be deterministic (no LLM): 4D from evidence signal phrases, 4E from counting /
  aggregating over `ComparableStartup` fields.
