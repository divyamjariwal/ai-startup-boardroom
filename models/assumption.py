"""Structured load-bearing assumptions and their deterministic ranking.

A specialist agent emits ``AssumptionDraft`` objects: things that must be true
for the startup to work, each self-rated for ``impact`` and ``uncertainty``.
:mod:`services.assumption_engine` deduplicates, scores, ranks, and attaches an
evidence status, producing ``RankedAssumption`` records. No scoring or ranking
logic lives in this module.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    UNCERTAIN = "uncertain"
    UNVERIFIED = "unverified"


class AssumptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, Field(pattern=r"^A-[A-Z]+-\d{3}$")]
    text: Annotated[str, Field(min_length=1, max_length=600)]
    category: Annotated[str, Field(min_length=1, max_length=40)]
    impact: Annotated[int, Field(ge=1, le=5)]
    uncertainty: Annotated[int, Field(ge=1, le=5)]
    supports_metric: Annotated[str, Field(pattern=r"^[a-z_]+_score$")] | None = None
    claim_ids: list[Annotated[str, Field(pattern=r"^C-[A-Z]+-\d{3}$")]] = Field(default_factory=list)


class RankedAssumption(AssumptionDraft):
    criticality: Annotated[int, Field(ge=1, le=25)]
    rank: Annotated[int, Field(ge=1)]
    evidence_status: EvidenceStatus
    decision_critical: bool
