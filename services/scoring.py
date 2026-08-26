"""Deterministic scoring with one convention: higher always means better."""

from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.decision import InvestmentDecision


def calculate_agent_score(scores: list[int]) -> float:
    """Return an agent score on a 0-100 scale from positive 1-10 metrics."""

    return round(sum(scores) / len(scores) * 10, 2)


def calculate_investor_score(investor: InvestorAgentResult) -> float:
    return calculate_agent_score([
        investor.market_score,
        investor.revenue_score,
        investor.scalability_score,
        investor.risk_management_score,
    ])


def calculate_cto_score(cto: CTOAgentResult) -> float:
    return calculate_agent_score([
        cto.technical_feasibility_score,
        cto.scalability_score,
        cto.infrastructure_simplicity_score,
        cto.security_posture_score,
        cto.cost_efficiency_score,
    ])


def calculate_marketing_score(marketing: MarketingAgentResult) -> float:
    return calculate_agent_score([
        marketing.customer_acquisition_score,
        marketing.brand_differentiation_score,
        marketing.growth_potential_score,
        marketing.go_to_market_score,
        marketing.retention_score,
    ])


def calculate_product_score(product: ProductAgentResult) -> float:
    return calculate_agent_score([
        product.product_market_fit_score,
        product.user_experience_score,
        product.feature_differentiation_score,
        product.retention_score,
        product.product_vision_score,
    ])


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
        return f"🟢 {InvestmentDecision.STRONG_INVESTMENT.value}"

    elif score >= 70:
        return f"🟡 {InvestmentDecision.PROCEED_WITH_CAUTION.value}"

    else:
        return f"🔴 {InvestmentDecision.HIGH_RISK.value}"
