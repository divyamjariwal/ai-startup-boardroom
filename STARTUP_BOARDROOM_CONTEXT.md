# Startup Boardroom — Session Context

Concise handoff for future sessions. Not an audit.

## 1. Product thesis

An **assumption & evidence engine for early-stage startup ideas**. The product's job is not to hand down a verdict; it exposes the load-bearing assumptions behind an idea, marks which are externally supported vs. unverified, shows which ones the decision hinges on, and points the founder at what to validate next. Scores are decision-support signal, not investment advice.

## 2. Current architecture (one diagram)

```
Idea
 → ResearchEngine (optional Tavily) → EvidenceStore (in-memory, per run)
 → 4 specialist agents (Investor / CTO / Marketing / Product), each given a filtered evidence package
     → self-reported claims → verify_claim() → VerifiedClaim{status, importance, supports_metric}
 → deterministic scoring (evidence-adjusted) → boardroom score → investment band
 → Debate agent + Chairperson/Summary agent (narrative only)
 → Streamlit UI (tabs, radar charts) + PDF report
```

Stack: Python 3.11, Streamlit, Groq API, Pydantic v2 (strict), Plotly, ReportLab.

## 3. Completed V1 features

- Six LLM roles: Investor, CTO, Marketing, Product, Debate moderator, Chairperson/Summary.
- Strict Pydantic schemas for every agent output.
- Deterministic 0–100 scoring per agent + averaged boardroom score with investment bands.
- Optional external research (Tavily) → typed `Evidence` with hostname-based source classification.
- Per-run `EvidenceStore`; agent claims verified against it (`verify_claim`).
- Executive dashboard, per-agent radar charts, Debate + Verdict tabs, Evidence & Sources tab, PDF export.

## 4. Step 1 changes (evidence now influences scores)

- **Evidence-aware scoring**: verified claims can now *discount* a specialist score. Evidence may only lower a score, never raise it. Wired into the existing `calculate_*_score` functions; no new orchestration, no UI change.
- **`supports_metric`**: one optional field added to `ClaimDraft` (`^[a-z_]+_score$` or `None`). A claim tagged with one of that agent's metric names discounts only that metric; untagged or non-matching claims discount all of the agent's metrics. Nothing is discarded. Prompts updated with one line each.
- **Verifier safety fixes** (so a status can be trusted by the scorer):
  - Cited evidence IDs that don't resolve can no longer yield `SUPPORTED` (no silent drop).
  - `UNKNOWN` source quality weight lowered to ≤ `LOW`.
  - A detected contradiction now yields `CONTRADICTED` even if weak supporting evidence also exists.
  - `SUPPORTED` requires at least one cited source of `MEDIUM`+ quality.
- Tests: `tests/test_models_and_scoring.py` — 3 pre-existing + 9 new, all pass.

## 5. Current scoring rule

```
status penalty:  SUPPORTED 0.00 · PARTIALLY_SUPPORTED 0.10 · UNCERTAIN 0.15 · UNSUPPORTED 0.25 · CONTRADICTED 0.40
per claim:       penalty = status_penalty × (importance / 5)
per metric:      total_penalty = agent-level penalties + penalties tagged to that metric
                 multiplier    = clamp(1 − total_penalty, 0.5, 1.0)
                 adjusted      = raw_metric(1–10) × 10 × multiplier
agent score:     mean of adjusted metrics, rounded to 2 dp
```

No claims ⇒ multiplier 1.0 ⇒ identical to the pre-Step-1 result. `confidence` and `evidence_coverage()` are deliberately not used for scoring.

## 6. Known limitation

The verifier is still **lexical / token-overlap** matching with a small negation blocklist. It has no semantic understanding: paraphrased contradictions and numeric misstatements can still pass as support. An evidence-adjusted score is only as reliable as bag-of-words matching. NLI/semantic verification is deferred.

## 7. Design constraints (keep these)

- Lightweight architecture; no major refactors.
- Deterministic Python logic wherever possible; prefer it over another LLM call.
- Avoid unnecessary new agents, databases, embeddings, external APIs, or frameworks.
- Keep changes small, explainable, and testable.
- **Historical startup evidence** (discover similar past startups, analyze their outcomes, blend with current market evidence) is a planned *core* future feature — design choices should not block it.

## 8. Next step

**Assumption Engine** — extract the load-bearing assumptions behind an idea, rank them by impact × uncertainty, and surface the decision-critical ones. Foundation for sensitivity analysis and founder validation plans. Not started.
