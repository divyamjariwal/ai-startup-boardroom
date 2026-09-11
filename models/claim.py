"""Claim contracts separating an agent's factual claims from interpretation."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from models.evidence import ResearchCategory


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNCERTAIN = "uncertain"
    NOT_VERIFIABLE = "not_verifiable"


class ClaimDraft(BaseModel):
    # LLM output arrives as plain JSON, so `category` is a string like "market" -
    # strict mode would require an actual ResearchCategory instance and always fail.
    model_config = ConfigDict(extra="forbid")

    claim_id: Annotated[str, Field(pattern=r"^C-[A-Z]+-\d{3}$")]
    text: Annotated[str, Field(min_length=1, max_length=600)]
    category: ResearchCategory
    source_evidence_ids: list[Annotated[str, Field(pattern=r"^E-\d{3}$")]] = Field(default_factory=list)
    importance: Annotated[int, Field(ge=1, le=5)] = 3
    supports_metric: Annotated[str, Field(pattern=r"^[a-z_]+_score$")] | None = None


class VerifiedClaim(ClaimDraft):
    status: ClaimStatus
    confidence: Annotated[float, Field(ge=0, le=1)]
    verification_notes: Annotated[str, Field(min_length=1)]
