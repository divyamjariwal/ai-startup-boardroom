"""Foundation schema for sourced evidence; not yet populated by the app."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claim: Annotated[str, Field(min_length=1)]
    source_url: HttpUrl
    source_title: Annotated[str, Field(min_length=1)]
    excerpt: Annotated[str, Field(min_length=1)]
