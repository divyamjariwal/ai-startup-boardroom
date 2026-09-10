# Startup Boardroom — Session Context

Concise handoff for future sessions. Not an audit.

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

## 9. Next step

**Historical Startup Discovery / Reference Class** — discover similar past startups, analyze
their outcomes, and blend that reference-class evidence with the current market evidence
(see the core-feature note in §8). Not started.
