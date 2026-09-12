# AI Startup Boardroom

AI Startup Boardroom is a Streamlit decision-support application that evaluates a startup idea
the way a real board would: from multiple expert perspectives, backed by external evidence where
possible, with every load-bearing assumption made explicit rather than buried inside a single
opaque score.

It combines structured LLM assessments, deterministic scoring, and a set of independent
analytical engines (evidence verification, assumption ranking, sensitivity analysis, founder
validation planning, and historical reference-class discovery) into one coherent report: an
executive dashboard, a boardroom debate and verdict, and a downloadable PDF.

The project is a transparent decision-support prototype. It does not give investment advice,
predict outcomes, or assign success probabilities — every analytical layer is designed to show
its reasoning and its evidence rather than hand down a verdict.

## What it does

Submit a startup idea and the application runs it through a full boardroom analysis pipeline:

**1. External research (optional, Tavily-backed).** If configured, the app searches for real
market, pricing, competitor, and regulatory evidence and classifies each source by quality
(government/academic/company/news/industry/community). Every fact any agent claims can be traced
back to a real, cited source.

**2. Four specialist AI roles**, each producing a structured, schema-validated assessment:

- **Investor** — market opportunity, revenue potential, scalability, risk management.
- **CTO** — technical feasibility, scalability, infrastructure simplicity, security posture, cost efficiency.
- **Marketing** — customer acquisition, brand differentiation, growth potential, go-to-market readiness, retention.
- **Product** — product-market fit, user experience, feature differentiation, retention, product vision.

Each specialist also emits factual **claims** (verified against the retrieved evidence — a claim
with no supporting source cannot count as "supported") and structured **assumptions** (necessary
conditions for the idea to succeed, not predictions).

**3. Evidence-aware scoring.** A specialist's score is only ever *discounted*, never boosted, by
weak or contradicted claims — an idea with no external evidence scores exactly as it would have
before evidence existed.

**4. Decision-critical assumption ranking.** Every assumption from every specialist is
deduplicated and ranked by **criticality = impact × uncertainty**, cross-referenced against its
evidence status (supported / partially supported / uncertain / unverified / contradicted).

**5. Sensitivity analysis.** For each decision-critical assumption, a "what if this turns out to
be false?" failure scenario shows how far the boardroom score — and the investment band — would
move. This is scenario analysis, not a forecast: no probabilities are assigned to any scenario.

**6. Founder validation plan.** A ranked, actionable checklist — for each assumption, a concrete
test (discovery interview, landing-page experiment, prototype test, pricing experiment, …), a test
question, a success signal, and a recommended sample size.

**7. Historical reference class (optional, Tavily-backed).** The app searches for real
past/current startups similar to the idea, checks what evidence-backed outcome they had (active,
acquired, public, shut down, pivoted, or unknown — never guessed), and surfaces bounded, sample-level
patterns ("3 of the 5 retrieved comparables shut down"). This layer is purely descriptive and is
kept independent of scoring and assumptions — it never feeds into either.

**8. Boardroom debate and verdict.** A debate moderator synthesizes the four specialist views into
agreements, disagreements, major risks, and strongest arguments; a chairperson agent then renders
a final boardroom verdict.

**9. PDF report.** Every layer above — scores, assumptions, sensitivity scenarios, validation plan,
reference class, and the final verdict — is compiled into a single downloadable report.

## Architecture

```text
Startup idea
    │
    ├── ResearchEngine (optional Tavily) ──► EvidenceStore
    │        │
    │        ▼
    ├── Investor ──┐
    ├── CTO ───────┤──► claims → verify_claim() → VerifiedClaim
    ├── Marketing ─┤──► evidence-adjusted specialist scores ──► boardroom score + band
    └── Product ───┘
              │
              ├──► AssumptionEngine   → ranked, decision-critical assumptions
              ├──► SensitivityEngine  → failure-scenario score deltas
              ├──► ValidationEngine   → founder validation plan
              │
              ├──► Debate agent + Chairperson agent → boardroom debate & verdict
              │
              └── (independent, read-only layer) ─────────────────────────────
                   IdeaProfile → discover_reference_class → verify_outcomes
                   → build_reference_class → comparable startups + patterns

                                    ▼
                    Streamlit UI (11 tabs) + PDF boardroom report
```

Each AI role follows the same execution contract:

```text
Prompt file + input → Groq LLM response → JSON parsing → strict Pydantic validation → typed result
```

Every deterministic engine (scoring, evidence verification, assumption ranking, sensitivity,
validation planning, similarity scoring, outcome classification, reference-class aggregation) is
plain, dependency-free Python — no additional LLM calls, no embeddings, no vector store. The only
two points where the app calls an LLM at all are the four specialist assessments plus the debate
and verdict synthesis, and — for the reference-class layer — a single extraction call per run to
turn search results into named comparable companies.

## Design principles

- **Evidence before opinion.** A specialist's score can be discounted by weak evidence but never
  inflated by it. No claim counts as "supported" without a real, resolvable, medium-or-better
  quality source.
- **Assumptions over verdicts.** The product's job is to expose what the idea depends on, not to
  declare whether it will succeed.
- **No fabricated probabilities.** Sensitivity scenarios, outcome confidence, and reference-class
  patterns are explicitly bounded, descriptive statements ("N of the M retrieved comparables…"),
  never population-level or predictive claims.
- **Deterministic wherever possible.** Every analytical engine beyond the four specialist calls
  and the debate/verdict synthesis is plain Python — transparent, testable, and reproducible.
- **Independent, non-contaminating layers.** The reference-class engine is read-only: it never
  feeds specialist scoring or the assumption engine, by design.
- **Graceful degradation.** Every external dependency (research provider, reference-class
  discovery) has an explicit "unavailable" status the UI handles cleanly — a missing API key never
  crashes the app, it just narrows what that run can show.

## Project structure

```text
ai-startup-boardroom/
├── agents/                        # Groq runner + one wrapper per AI role
│   ├── base_agent.py              #   shared prompt → JSON → Pydantic pipeline
│   ├── investor.py / cto.py / marketing.py / product.py
│   ├── debate.py / summary.py
├── models/                        # Strict Pydantic schemas (the app's typed contracts)
│   ├── startup.py, decision.py
│   ├── evidence.py, claim.py, agent_result.py
│   ├── assumption.py, sensitivity.py, validation.py
│   └── reference_class.py         #   idea profile, candidates, comparables, patterns
├── services/                      # Deterministic engines and infrastructure
│   ├── research.py, evidence_store.py, verifier.py, scoring.py
│   ├── assumption_engine.py, sensitivity_engine.py, validation_engine.py
│   ├── idea_profile.py, similarity.py, reference_discovery.py,
│   │   reference_outcomes.py, reference_class_engine.py
│   └── pdf_generator.py
├── prompts/                       # Versioned role instructions & JSON contracts
├── components/                    # Streamlit cards, charts, dashboard widgets
├── tests/                         # Full regression suite (offline, no live network/LLM)
├── streamlit_app.py               # Primary application entry point (11 tabs)
├── STARTUP_BOARDROOM_CONTEXT.md   # Full engineering history & architectural decisions
├── requirements.txt
└── runtime.txt
```

## Getting started

### Prerequisites

- Python 3.11
- A [Groq](https://console.groq.com) API key (required — powers the specialist, debate, and
  verdict agents)
- A [Tavily](https://tavily.com) API key (optional — enables external market research and the
  historical reference-class feature; without it, those layers report themselves as unavailable
  and the rest of the app runs normally)

### Installation

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
# Optional: defaults to openai/gpt-oss-120b
GROQ_MODEL=openai/gpt-oss-120b

# Optional: enables external research + the Reference Class tab
TAVILY_API_KEY=your_tavily_api_key
```

### Run the application

```bash
streamlit run streamlit_app.py
```

### Run the test suite

```bash
python -m unittest discover -s tests
```

The suite runs entirely offline — every test injects a fake research provider and a stub LLM
extractor, so it never makes a live network or Groq call and stays deterministic regardless of
what's in your local `.env`.

## Technology stack

- Python 3.11
- Streamlit — UI
- Groq API (`openai/gpt-oss-120b` by default, overridable via `GROQ_MODEL`) — the four
  specialists, the debate moderator, and the chairperson
- Tavily API — optional external research and reference-class discovery
- Pydantic v2 (strict schemas) — every AI output and every internal data contract
- Plotly — radar charts and interactive visuals
- ReportLab — PDF report generation

## Current scope and limitations

- The claim verifier and the reference-class outcome classifier are both lexical / keyword-based,
  not semantic — paraphrased claims or outcomes can be missed. Both deliberately err toward
  "unverified" / "unknown" rather than guessing.
- Reference-class discovery is bounded to 2 searches and up to 6 candidates per idea, by design,
  to stay lightweight — niche or vaguely-described ideas may return no matches.
- Sensitivity scenarios use a fixed, transparent penalty model, not a calibrated forecast — they
  illustrate "what if this fails," not "how likely is this to fail."
- No persistent analysis history, authentication, or multi-round agent debate yet.
- Outputs are structured decision-support material, not verified due diligence or investment
  advice.

## Screenshots

### Executive dashboard

![Executive Dashboard](screenshots/dashboard.png)

### Boardroom debate

![Boardroom Debate](screenshots/debate.png)

### Final verdict

![Final Verdict](screenshots/verdict.png)

## Author

Divyam Jariwal
