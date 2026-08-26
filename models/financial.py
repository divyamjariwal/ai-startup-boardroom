"""Foundation schema for future deterministic financial projections."""

from pydantic import BaseModel, ConfigDict, Field


class FinancialProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    annual_recurring_revenue: float = Field(ge=0)
    gross_margin_percent: float = Field(ge=0, le=100)
    monthly_burn: float = Field(ge=0)
    runway_months: float = Field(ge=0)
