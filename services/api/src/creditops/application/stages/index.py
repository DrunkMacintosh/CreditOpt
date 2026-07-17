from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class IndexedPassage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page: int = Field(ge=1)
    text: str = Field(min_length=1)
    embedding: tuple[float, ...] = Field(min_length=1)
    embedding_model_id: str = Field(min_length=1)


def validate_embedding(
    values: Sequence[float], *, expected_dimension: int | None = None
) -> tuple[float, ...]:
    if not values:
        raise ValueError("embedding cannot be empty")
    if expected_dimension is not None and len(values) != expected_dimension:
        raise ValueError("embedding dimension does not match the configured model")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("embedding contains a non-finite value")
    return result
