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
 → Debate agent + Chairperson/Summary agent (narrative only)
 → Streamlit UI (tabs incl. Assumptions, radar charts) + PDF report (incl. assumptions section)
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

## 8. Design constraints (keep these)

- Lightweight architecture; no major refactors.
- Deterministic Python logic wherever possible; prefer it over another LLM call.
- Avoid unnecessary new agents, databases, embeddings, external APIs, dependencies, or frameworks.
- Keep changes small, explainable, and testable.
- **Historical startup evidence** (discover similar past startups, analyze their outcomes, blend
  with current market evidence) is a planned *core* future feature — design choices should not
  block it.

## 9. Next step

**Sensitivity Analysis + Validation Plan** — use the ranked assumptions to show how the boardroom
outcome moves as decision-critical assumptions flip, and generate a founder-facing plan for what
to validate first. Not started.
