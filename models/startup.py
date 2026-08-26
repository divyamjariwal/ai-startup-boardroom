"""Input model for a startup submitted to the boardroom."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StartupIdea(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    description: Annotated[str, Field(min_length=1, max_length=10_000)]
