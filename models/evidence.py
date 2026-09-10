"""Typed evidence contracts. Evidence is external data, never agent opinion."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ResearchCategory(str, Enum):
    MARKET = "market"
    CUSTOMERS = "customers"
    COMPETITORS = "competitors"
    PRICING = "pricing"
    INDUSTRY_TRENDS = "industry_trends"
    TECHNOLOGY = "technology"
    BUSINESS_MODEL = "business_model"
    REGULATORY = "regulatory"


class SourceType(str, Enum):
    GOVERNMENT = "government_regulatory"
    ACADEMIC = "academic_research"
    COMPANY = "company_primary"
    NEWS = "established_news"
    INDUSTRY = "industry_report"
    PROFESSIONAL = "professional_organization"
    COMMUNITY = "community_forum"
    UNKNOWN = "unknown"


class SourceQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: Annotated[str, Field(pattern=r"^E-\d{3}$")]
    category: ResearchCategory
    topic: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    source_url: HttpUrl
    source_name: Annotated[str, Field(min_length=1)]
    source_type: SourceType
    source_quality: SourceQuality
    excerpt: Annotated[str, Field(min_length=1, max_length=2_000)]
    relevance_score: Annotated[float, Field(ge=0, le=1)]
    publication_date: datetime | None = None
    retrieved_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)
