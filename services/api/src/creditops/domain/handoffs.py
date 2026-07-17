from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from creditops.domain.evidence import ConfirmedFact
from creditops.domain.ids import (
    CandidateFactId,
    CaseId,
    ConfirmedFactId,
    ConflictId,
    EvidenceGapId,
    HandoffId,
)

HANDOFF_READY_STATE: Literal["READY_FOR_SPECIALIST_REVIEW"] = "READY_FOR_SPECIALIST_REVIEW"


class HandoffArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: HandoffId
    case_id: CaseId
    case_version: int = Field(ge=1)
    state: Literal["READY_FOR_SPECIALIST_REVIEW"] = HANDOFF_READY_STATE
    confirmed_facts: tuple[ConfirmedFact, ...] = ()
    open_candidate_ids: tuple[CandidateFactId, ...] = ()
    unsupported_fact_ids: tuple[ConfirmedFactId, ...] = ()
    conflict_ids: tuple[ConflictId, ...] = ()
    gap_ids: tuple[EvidenceGapId, ...] = ()
    stale: bool = False

    @model_validator(mode="after")
    def contains_only_supported_evidence(self) -> Self:
        _check_handoff(self)
        return self


def _check_handoff(artifact: HandoffArtifact) -> None:
    if artifact.case_version < 1:
        raise ValueError("handoff must bind to a positive case version")
    if artifact.state != HANDOFF_READY_STATE:
        raise ValueError("handoff is not ready for specialist review")
    if artifact.open_candidate_ids:
        raise ValueError("handoff cannot contain open candidates")
    if artifact.unsupported_fact_ids:
        raise ValueError("handoff cannot contain unsupported facts")
    if any(not hasattr(fact, "source") or fact.source is None for fact in artifact.confirmed_facts):
        raise ValueError("handoff facts require source regions")


def validate_handoff(artifact: HandoffArtifact) -> HandoffArtifact:
    _check_handoff(artifact)
    return artifact
