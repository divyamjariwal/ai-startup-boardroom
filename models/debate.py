"""Schema for the moderator's single-round boardroom synthesis."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ThreePoints = Annotated[list[str], Field(min_length=3, max_length=3)]


class DebateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agreements: ThreePoints
    disagreements: ThreePoints
    major_risks: ThreePoints
    strongest_arguments: ThreePoints
    debate_summary: Annotated[str, Field(min_length=1)]
