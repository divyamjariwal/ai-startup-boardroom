"""Deterministic failure-scenario analysis over decision-critical assumptions.

Given the four specialist assessments and the ranked assumptions,
:mod:`services.sensitivity_engine` asks one question per decision-critical
assumption: *if this assumption proves false, how far does the boardroom
outcome move?* The penalty is a fixed, transparent formula -- never an LLM
guess and never a probability. Scenario records here describe hypothetical
failure worlds, not forecasts.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Language the UI and PDF must use for these records.
FAILURE_SCENARIO_LABEL = "Failure scenario"
FAILURE_SCENARIO_PREFIX = "If this assumption proves false"
SENSITIVITY_DISCLAIMER = "Scenario analysis - not a prediction."


class MappingStatus(str, Enum):
    """How (or whether) an assumption was tied to the score model."""

    MAPPED_METRIC = "mapped_metric"
    MAPPED_SPECIALIST = "mapped_specialist"
    UNMAPPED = "unmapped"


class SensitivityScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    assumption_id: str
    assumption_text: str
    category: str
    impact: Annotated[int, Field(ge=1, le=5)]
    uncertainty: Annotated[int, Field(ge=1, le=5)]
    criticality: Annotated[int, Field(ge=1, le=25)]
    decision_critical: bool

    mapping_status: MappingStatus
    affected_specialists: list[str] = Field(default_factory=list)
    affected_metric: str | None = None
    scenario_penalty: float

    current_boardroom_score: Annotated[int, Field(ge=0, le=100)]
    # None only when mapping_status is UNMAPPED: we refuse to manufacture a delta.
    scenario_boardroom_score: int | None = None
    score_delta: int | None = None
    current_band: str
    scenario_band: str | None = None
    band_changed: bool = False

    note: str


class SensitivityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    current_boardroom_score: Annotated[int, Field(ge=0, le=100)]
    current_band: str
    scenarios: list[SensitivityScenario] = Field(default_factory=list)
    decision_critical_count: int
    band_changing_count: int
    disclaimer: str = SENSITIVITY_DISCLAIMER
