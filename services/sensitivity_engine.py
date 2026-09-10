"""Deterministic failure-scenario analysis for decision-critical assumptions.

For each decision-critical ``RankedAssumption`` we build one hypothetical copy
of the boardroom outcome in which that assumption has failed, and report how
far the score and investment band move. Nothing here calls an LLM, and no
stored score is mutated: the specialist scorers are called on the original
``AgentResult`` objects and the penalty is applied to copies of their numbers.

Penalty model (fixed and transparent)::

    scenario_penalty = 0.20 * (impact / 5) * (uncertainty / 5)

applied only in the "assumption failed" world.

* ``supports_metric`` names a metric of an owning specialist -> the penalty
  hits that raw metric directly (``metric * (1 - scenario_penalty)``) and the
  specialist score is recomputed with the existing aggregation rule in
  :mod:`services.scoring` (evidence adjustment still applies on top).
* no ``supports_metric`` -> the whole owning specialist score is scaled by
  ``(1 - scenario_penalty)``.
* neither can be resolved -> ``UNMAPPED``; no score delta is produced. An
  explicit gap beats fake precision.

Merged assumptions are applied independently to each owning specialist.
"""

from models.agent_result import (
    AgentResult,
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.assumption import RankedAssumption
from models.sensitivity import (
    FAILURE_SCENARIO_PREFIX,
    MappingStatus,
    SensitivityResult,
    SensitivityScenario,
)
from services.assumption_engine import _normalize
from services.scoring import (
    _evidence_adjusted_score,
    calculate_cto_score,
    calculate_investor_score,
    calculate_marketing_score,
    calculate_product_score,
    get_investment_decision,
)

SCENARIO_PENALTY_BASE = 0.20
_SCORE_FLOOR = 0.0
_SCORE_CEILING = 100.0

# Metric field names per specialist. These mirror the dicts built inside
# services/scoring.py; models/agent_result.py is the source of truth for the
# names themselves (the getattr calls below would fail loudly on a typo).
_SPECIALIST_METRICS: dict[str, tuple[str, ...]] = {
    "Investor": (
        "market_score",
        "revenue_score",
        "scalability_score",
        "risk_management_score",
    ),
    "CTO": (
        "technical_feasibility_score",
        "scalability_score",
        "infrastructure_simplicity_score",
        "security_posture_score",
        "cost_efficiency_score",
    ),
    "Marketing": (
        "customer_acquisition_score",
        "brand_differentiation_score",
        "growth_potential_score",
        "go_to_market_score",
        "retention_score",
    ),
    "Product": (
        "product_market_fit_score",
        "user_experience_score",
        "feature_differentiation_score",
        "retention_score",
        "product_vision_score",
    ),
}

_SPECIALIST_SCORERS = {
    "Investor": calculate_investor_score,
    "CTO": calculate_cto_score,
    "Marketing": calculate_marketing_score,
    "Product": calculate_product_score,
}

_SPECIALIST_ORDER = ("Investor", "CTO", "Marketing", "Product")


def clamp_score(value: float) -> float:
    """Confine a score to the 0-100 range."""

    return min(_SCORE_CEILING, max(_SCORE_FLOOR, value))


def _scenario_penalty(impact: int, uncertainty: int) -> float:
    return SCENARIO_PENALTY_BASE * (impact / 5) * (uncertainty / 5)


def _aggregate_boardroom(scores: dict[str, float]) -> int:
    """Mean of the four specialist scores, rounded.

    Mirrors :func:`services.scoring.calculate_boardroom_score`.
    """

    return round(sum(scores[name] for name in _SPECIALIST_ORDER) / len(_SPECIALIST_ORDER))


def _owning_specialists(
    assumption: RankedAssumption,
    results_by_name: dict[str, AgentResult],
) -> list[str]:
    """Specialists whose original assumptions include this (normalized) text."""

    key = _normalize(assumption.text)
    owners: list[str] = []
    for name in _SPECIALIST_ORDER:
        result = results_by_name[name]
        if any(_normalize(draft.text) == key for draft in result.assumptions):
            owners.append(name)
    return owners


def _metric_adjusted_specialist_score(
    name: str,
    result: AgentResult,
    metric: str,
    penalty: float,
) -> float:
    """Recompute a specialist score with one raw metric reduced by ``penalty``.

    Uses the exact aggregation rule from :mod:`services.scoring` so evidence
    adjustment still applies on top of the scenario penalty. The original
    ``result`` is never mutated -- only a local dict of its metric values.
    """

    metric_scores: dict[str, float] = {
        field: getattr(result, field) for field in _SPECIALIST_METRICS[name]
    }
    metric_scores[metric] = metric_scores[metric] * (1 - penalty)
    return clamp_score(_evidence_adjusted_score(metric_scores, result.verified_claims))


def _pct(penalty: float) -> float:
    return round(penalty * 100, 1)


def run_sensitivity(
    investor: InvestorAgentResult,
    cto: CTOAgentResult,
    marketing: MarketingAgentResult,
    product: ProductAgentResult,
    current_boardroom_score: int,
    current_band: str,
    ranked_assumptions: list[RankedAssumption],
) -> SensitivityResult:
    """Build one failure scenario per decision-critical ranked assumption."""

    results_by_name: dict[str, AgentResult] = {
        "Investor": investor,
        "CTO": cto,
        "Marketing": marketing,
        "Product": product,
    }

    # Computed once from the untouched originals; every scenario branches from here.
    current_scores = {
        name: _SPECIALIST_SCORERS[name](results_by_name[name])
        for name in _SPECIALIST_ORDER
    }

    critical = [item for item in ranked_assumptions if item.decision_critical]
    scenarios: list[SensitivityScenario] = []

    for assumption in critical:
        penalty = _scenario_penalty(assumption.impact, assumption.uncertainty)
        owners = _owning_specialists(assumption, results_by_name)
        metric = assumption.supports_metric

        common = dict(
            assumption_id=assumption.id,
            assumption_text=assumption.text,
            category=assumption.category,
            impact=assumption.impact,
            uncertainty=assumption.uncertainty,
            criticality=assumption.criticality,
            decision_critical=assumption.decision_critical,
            scenario_penalty=round(penalty, 4),
            current_boardroom_score=current_boardroom_score,
            current_band=current_band,
        )

        if not owners:
            scenarios.append(
                SensitivityScenario(
                    **common,
                    mapping_status=MappingStatus.UNMAPPED,
                    note=(
                        "Assumption text matches no specialist's assumptions; "
                        "cannot attribute a score impact without inventing a mapping."
                    ),
                )
            )
            continue

        scenario_scores = dict(current_scores)

        if metric is not None:
            metric_owners = [n for n in owners if metric in _SPECIALIST_METRICS[n]]
            if not metric_owners:
                scenarios.append(
                    SensitivityScenario(
                        **common,
                        mapping_status=MappingStatus.UNMAPPED,
                        affected_specialists=owners,
                        note=(
                            f"supports_metric '{metric}' is not a metric of the owning "
                            f"specialist(s) {', '.join(owners)}; not mapped, to avoid "
                            "fake precision."
                        ),
                    )
                )
                continue
            for n in metric_owners:
                scenario_scores[n] = _metric_adjusted_specialist_score(
                    n, results_by_name[n], metric, penalty
                )
            mapping_status = MappingStatus.MAPPED_METRIC
            affected = metric_owners
            affected_metric = metric
            note = (
                f"{FAILURE_SCENARIO_PREFIX}: metric '{metric}' deteriorates by the "
                f"modeled penalty ({_pct(penalty)}%) for "
                f"{', '.join(metric_owners)}."
            )
        else:
            for n in owners:
                scenario_scores[n] = clamp_score(current_scores[n] * (1 - penalty))
            mapping_status = MappingStatus.MAPPED_SPECIALIST
            affected = owners
            affected_metric = None
            note = (
                f"{FAILURE_SCENARIO_PREFIX}: no single metric is named, so the whole "
                f"{', '.join(owners)} score absorbs the modeled penalty "
                f"({_pct(penalty)}%)."
            )

        scenario_board = _aggregate_boardroom(scenario_scores)
        scenario_band = get_investment_decision(scenario_board)
        scenarios.append(
            SensitivityScenario(
                **common,
                mapping_status=mapping_status,
                affected_specialists=affected,
                affected_metric=affected_metric,
                scenario_boardroom_score=scenario_board,
                score_delta=scenario_board - current_boardroom_score,
                scenario_band=scenario_band,
                band_changed=scenario_band != current_band,
                note=note,
            )
        )

    band_changing = sum(1 for scenario in scenarios if scenario.band_changed)
    return SensitivityResult(
        current_boardroom_score=current_boardroom_score,
        current_band=current_band,
        scenarios=scenarios,
        decision_critical_count=len(critical),
        band_changing_count=band_changing,
    )
