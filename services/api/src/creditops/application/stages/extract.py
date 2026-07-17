from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from creditops.application.stages.parse import ParsedDocument, ParsedRegion


class ExtractionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field_key: str = Field(min_length=1, max_length=120)
    proposed_value: str | int | float | bool
    confidence: float = Field(ge=0, le=1)
    page: int = Field(ge=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def valid_region(self) -> ExtractionCandidate:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("source region exceeds normalized page")
        return self


def _overlaps(candidate: ExtractionCandidate, region: ParsedRegion) -> bool:
    return bool(
        candidate.page == region.page
        and candidate.x < region.x + region.width
        and candidate.x + candidate.width > region.x
        and candidate.y < region.y + region.height
        and candidate.y + candidate.height > region.y
    )


def validate_candidates(
    candidates: Iterable[ExtractionCandidate],
    parsed: ParsedDocument,
) -> list[ExtractionCandidate]:
    regions = parsed.regions
    validated: list[ExtractionCandidate] = []
    for candidate in candidates:
        if candidate.x + candidate.width > 1 or candidate.y + candidate.height > 1:
            raise ValueError("candidate source region exceeds normalized page")
        if not any(_overlaps(candidate, region) for region in regions):
            raise ValueError("candidate has no addressable source region")
        validated.append(candidate)
    return validated


def extraction_schema(document_family: str) -> dict[str, Any]:
    # The model can propose candidates only.  The schema deliberately has no
    # confirmation, approval, score, or workflow-transition field.
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "field_key",
                        "proposed_value",
                        "confidence",
                        "page",
                        "x",
                        "y",
                        "width",
                        "height",
                    ],
                    "properties": {
                        "field_key": {"type": "string", "minLength": 1},
                        "proposed_value": {},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "page": {"type": "integer", "minimum": 1},
                        "x": {"type": "number", "minimum": 0, "maximum": 1},
                        "y": {"type": "number", "minimum": 0, "maximum": 1},
                        "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                        "height": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                    },
                },
            },
            "document_family": {"const": document_family},
        },
    }
