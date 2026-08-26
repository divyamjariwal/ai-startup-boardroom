"""Schemas for boardroom recommendations and final summaries."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ThreePoints = Annotated[list[str], Field(min_length=3, max_length=3)]


class InvestmentDecision(str, Enum):
    STRONG_INVESTMENT = "STRONG INVESTMENT"
    PROCEED_WITH_CAUTION = "PROCEED WITH CAUTION"
    HIGH_RISK = "HIGH RISK"


class SummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agreements: ThreePoints
    disagreements: ThreePoints
    opportunities: ThreePoints
    risks: ThreePoints
    final_verdict: Annotated[str, Field(min_length=1)]
