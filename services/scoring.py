"""Deterministic scoring with one convention: higher always means better."""

from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.claim import ClaimStatus, VerifiedClaim
from models.decision import InvestmentDecision

# Verified evidence may only discount an optimistic score, never raise it.
_STATUS_PENALTY = {
    ClaimStatus.SUPPORTED: 0.00,
    ClaimStatus.PARTIALLY_SUPPORTED: 0.10,
    ClaimStatus.UNCERTAIN: 0.15,
    ClaimStatus.UNSUPPORTED: 0.25,
    ClaimStatus.CONTRADICTED: 0.40,
}
_MULTIPLIER_FLOOR = 0.5


def calculate_agent_score(scores: list[int]) -> float:
    """Return an agent score on a 0-100 scale from positive 1-10 metrics."""

    return round(sum(scores) / len(scores) * 10, 2)


def _claim_penalty(claim: VerifiedClaim) -> float:
    return _STATUS_PENALTY.get(claim.status, 0.0) * (claim.importance / 5)


def _evidence_adjusted_score(
    metric_scores: dict[str, int],
    verified_claims: list[VerifiedClaim],
) -> float:
    """Average 1-10 metrics on a 0-100 scale after applying evidence penalties.

    A claim whose ``supports_metric`` names one of this agent's metrics only
    discounts that metric; every other claim discounts the whole agent. The
    per-metric multiplier is clamped to ``[_MULTIPLIER_FLOOR, 1.0]`` so evidence
    can never raise a score and can never more than halve one. With no claims the
    result is identical to ``calculate_agent_score``.
    """

    per_metric_penalty = {name: 0.0 for name in metric_scores}
    agent_level_penalty = 0.0
    for claim in verified_claims:
        target = claim.supports_metric
        if target in per_metric_penalty:
            per_metric_penalty[target] += _claim_penalty(claim)
        else:
            agent_level_penalty += _claim_penalty(claim)

    adjusted = []
    for name, raw in metric_scores.items():
        total_penalty = agent_level_penalty + per_metric_penalty[name]
        multiplier = min(1.0, max(_MULTIPLIER_FLOOR, 1.0 - total_penalty))
        adjusted.append(raw * 10 * multiplier)
    return round(sum(adjusted) / len(adjusted), 2)


def calculate_investor_score(investor: InvestorAgentResult) -> float:
    return _evidence_adjusted_score(
        {
            "market_score": investor.market_score,
            "revenue_score": investor.revenue_score,
            "scalability_score": investor.scalability_score,
            "risk_management_score": investor.risk_management_score,
        },
        investor.verified_claims,
    )


def calculate_cto_score(cto: CTOAgentResult) -> float:
    return _evidence_adjusted_score(
        {
            "technical_feasibility_score": cto.technical_feasibility_score,
            "scalability_score": cto.scalability_score,
            "infrastructure_simplicity_score": cto.infrastructure_simplicity_score,
            "security_posture_score": cto.security_posture_score,
            "cost_efficiency_score": cto.cost_efficiency_score,
        },
        cto.verified_claims,
    )


def calculate_marketing_score(marketing: MarketingAgentResult) -> float:
    return _evidence_adjusted_score(
        {
            "customer_acquisition_score": marketing.customer_acquisition_score,
            "brand_differentiation_score": marketing.brand_differentiation_score,
            "growth_potential_score": marketing.growth_potential_score,
            "go_to_market_score": marketing.go_to_market_score,
            "retention_score": marketing.retention_score,
        },
        marketing.verified_claims,
    )


def calculate_product_score(product: ProductAgentResult) -> float:
    return _evidence_adjusted_score(
        {
            "product_market_fit_score": product.product_market_fit_score,
            "user_experience_score": product.user_experience_score,
            "feature_differentiation_score": product.feature_differentiation_score,
            "retention_score": product.retention_score,
            "product_vision_score": product.product_vision_score,
        },
        product.verified_claims,
    )


def calculate_boardroom_score(
    investor: InvestorAgentResult,
    cto: CTOAgentResult,
    marketing: MarketingAgentResult,
    product: ProductAgentResult,
) -> int:
    """Average all four consistently normalized specialist scores."""

    return round(sum([
        calculate_investor_score(investor),
        calculate_cto_score(cto),
        calculate_marketing_score(marketing),
        calculate_product_score(product),
    ]) / 4)


def get_investment_decision(score: int) -> str:

    if score >= 85:
        return InvestmentDecision.STRONG_INVESTMENT.value

    elif score >= 70:
        return InvestmentDecision.PROCEED_WITH_CAUTION.value

    else:
        return InvestmentDecision.HIGH_RISK.value
