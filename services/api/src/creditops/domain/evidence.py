from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from creditops.domain.enums import FactDisposition
from creditops.domain.ids import (
    ActorId,
    CandidateFactId,
    ConfirmedFactId,
    DocumentVersionId,
    FactConfirmationId,
)

type FactValue = str | int | float | bool


class PageRegion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page: int = Field(ge=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_page(self) -> Self:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("region exceeds normalized page")
        return self


class CandidateFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: CandidateFactId
    document_version_id: DocumentVersionId
    field_key: str = Field(min_length=1)
    proposed_value: FactValue
    confidence: float = Field(ge=0, le=1)
    source: PageRegion


class FactConfirmation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: FactConfirmationId
    candidate_id: CandidateFactId
    disposition: FactDisposition
    actor_id: ActorId
    corrected_value: FactValue | None = None

    @model_validator(mode="after")
    def corrected_value_matches_disposition(self) -> Self:
        if self.disposition is FactDisposition.CORRECTED and self.corrected_value is None:
            raise ValueError("corrected_value is required for a corrected fact")
        if self.disposition is not FactDisposition.CORRECTED and self.corrected_value is not None:
            raise ValueError("corrected_value is only valid for a corrected fact")
        return self


class ConfirmedFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: ConfirmedFactId
    candidate_id: CandidateFactId
    confirmation_id: FactConfirmationId
    document_version_id: DocumentVersionId
    field_key: str = Field(min_length=1)
    value: FactValue
    candidate_value: FactValue
    source: PageRegion
    confirmed_by: ActorId

    @classmethod
    def from_confirmation(
        cls,
        *,
        id: ConfirmedFactId,
        candidate: CandidateFact,
        confirmation: FactConfirmation,
    ) -> Self:
        if confirmation.candidate_id != candidate.id:
            raise ValueError("confirmation does not reference the candidate")
        if confirmation.disposition is FactDisposition.ACCEPTED:
            value = candidate.proposed_value
        elif confirmation.disposition is FactDisposition.CORRECTED:
            if confirmation.corrected_value is None:
                raise ValueError("corrected confirmation has no corrected_value")
            value = confirmation.corrected_value
        else:
            raise ValueError(
                f"{confirmation.disposition.value} does not support a confirmed fact"
            )

        return cls(
            id=id,
            candidate_id=candidate.id,
            confirmation_id=confirmation.id,
            document_version_id=candidate.document_version_id,
            field_key=candidate.field_key,
            value=value,
            candidate_value=candidate.proposed_value,
            source=candidate.source,
            confirmed_by=confirmation.actor_id,
        )
