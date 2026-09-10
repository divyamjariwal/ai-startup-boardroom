"""Founder-facing validation plan derived from ranked assumptions.

:mod:`services.validation_engine` turns each ``RankedAssumption`` into one
concrete next test: a method, a question, a success signal, and a suggested
sample size. Everything is chosen by deterministic category templates -- no
LLM call. The methods and thresholds are suggestions, not universal
benchmarks.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.assumption import EvidenceStatus

# Priority ladder over criticality (impact x uncertainty). Decision-critical
# assumptions (criticality >= 16) therefore always land at HIGH or above.
PRIORITY_VERY_HIGH_MIN = 20
PRIORITY_HIGH_MIN = 16
PRIORITY_MEDIUM_MIN = 12

# Suggested sample sizes, kept as named constants so they are easy to tune.
SAMPLE_INTERVIEWS = 10
SAMPLE_PRICING = 10
SAMPLE_ACQUISITION = 50
SAMPLE_RETENTION_PILOT = 10
SAMPLE_TECH_PROTOTYPE = 1

VALIDATION_DISCLAIMER = (
    "Suggested validation methods and thresholds - not universal benchmarks."
)


class Priority(str, Enum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ValidationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rank: Annotated[int, Field(ge=1)]
    assumption_id: str
    assumption_text: str
    priority: Priority
    criticality: Annotated[int, Field(ge=1, le=25)]
    evidence_status: EvidenceStatus
    validation_method: str
    test_question: str
    success_signal: str
    recommended_sample: str
    rationale: str


class ValidationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ValidationItem] = Field(default_factory=list)
    disclaimer: str = VALIDATION_DISCLAIMER
