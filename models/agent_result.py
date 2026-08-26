"""Strict, positive-orientation schemas for specialist agent assessments."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[int, Field(ge=1, le=10)]
ThreePoints = Annotated[list[str], Field(min_length=3, max_length=3)]


class AgentResult(BaseModel):
    """Fields shared by each specialist's assessment."""

    model_config = ConfigDict(extra="forbid", strict=True)

    strengths: ThreePoints
    weaknesses: ThreePoints
    recommendation: Annotated[str, Field(min_length=1)]


class InvestorAgentResult(AgentResult):
    market_score: Score
    revenue_score: Score
    scalability_score: Score
    risk_management_score: Score


class CTOAgentResult(AgentResult):
    technical_feasibility_score: Score
    scalability_score: Score
    infrastructure_simplicity_score: Score
    security_posture_score: Score
    cost_efficiency_score: Score


class MarketingAgentResult(AgentResult):
    customer_acquisition_score: Score
    brand_differentiation_score: Score
    growth_potential_score: Score
    go_to_market_score: Score
    retention_score: Score


class ProductAgentResult(AgentResult):
    product_market_fit_score: Score
    user_experience_score: Score
    feature_differentiation_score: Score
    retention_score: Score
    product_vision_score: Score
