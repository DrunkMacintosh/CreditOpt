from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from creditops.domain.enums import FactDisposition
from creditops.domain.evidence import CandidateFact, ConfirmedFact, FactConfirmation
from creditops.domain.ids import (
    CandidateFactId,
    CaseId,
    ConflictId,
    EvidenceGapId,
    FactConfirmationId,
    HandoffId,
)

HANDOFF_READY_STATE: Literal["READY_FOR_SPECIALIST_REVIEW"] = "READY_FOR_SPECIALIST_REVIEW"


class HandoffArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: HandoffId
    case_id: CaseId
    case_version: int = Field(ge=1)
    state: Literal["READY_FOR_SPECIALIST_REVIEW"] = HANDOFF_READY_STATE
    candidates: tuple[CandidateFact, ...] = ()
    confirmations: tuple[FactConfirmation, ...] = ()
    confirmed_facts: tuple[ConfirmedFact, ...] = ()
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
    candidates_by_id: dict[CandidateFactId, CandidateFact] = {}
    for candidate in artifact.candidates:
        if candidate.case_id != artifact.case_id or candidate.case_version != artifact.case_version:
            raise ValueError("handoff evidence must share one case/version")
        if candidate.id in candidates_by_id:
            raise ValueError("handoff cannot contain duplicate candidate IDs")
        candidates_by_id[candidate.id] = candidate

    confirmations_by_candidate: dict[CandidateFactId, FactConfirmation] = {}
    confirmation_ids: set[FactConfirmationId] = set()
    for confirmation in artifact.confirmations:
        authority = confirmation.authority
        if authority.case_id != artifact.case_id or authority.case_version != artifact.case_version:
            raise ValueError("handoff evidence must share one case/version")
        if confirmation.id in confirmation_ids:
            raise ValueError("handoff cannot contain duplicate confirmation IDs")
        confirmation_ids.add(confirmation.id)
        if confirmation.candidate_id not in candidates_by_id:
            raise ValueError("handoff confirmation references an unknown candidate")
        if confirmation.candidate_id in confirmations_by_candidate:
            raise ValueError("each candidate requires exactly one disposition")
        confirmations_by_candidate[confirmation.candidate_id] = confirmation

    missing_confirmation_ids = candidates_by_id.keys() - confirmations_by_candidate.keys()
    if missing_confirmation_ids:
        raise ValueError("handoff has a missing confirmation for a candidate")

    supported_dispositions = {FactDisposition.ACCEPTED, FactDisposition.CORRECTED}
    facts_by_confirmation: dict[FactConfirmationId, ConfirmedFact] = {}
    for fact in artifact.confirmed_facts:
        if fact.case_id != artifact.case_id or fact.case_version != artifact.case_version:
            raise ValueError("handoff evidence must share one case/version")
        if not hasattr(fact, "source") or fact.source is None:
            raise ValueError("handoff facts require a source region")
        matched_candidate = candidates_by_id.get(fact.candidate_id)
        matched_confirmation = confirmations_by_candidate.get(fact.candidate_id)
        if matched_candidate is None or matched_confirmation is None:
            raise ValueError("handoff fact does not reference confirmed candidate evidence")
        if matched_confirmation.disposition not in supported_dispositions:
            raise ValueError("handoff fact has an unsupported disposition")
        if fact.confirmation_id in facts_by_confirmation:
            raise ValueError("each supported confirmation requires exactly one confirmed fact")
        facts_by_confirmation[fact.confirmation_id] = fact
        expected_value = (
            matched_candidate.proposed_value
            if matched_confirmation.disposition is FactDisposition.ACCEPTED
            else matched_confirmation.corrected_value
        )
        if (
            fact.confirmation_id != matched_confirmation.id
            or fact.document_version_id != matched_candidate.document_version_id
            or fact.field_key != matched_candidate.field_key
            or fact.candidate_value != matched_candidate.proposed_value
            or fact.value != expected_value
            or fact.source != matched_candidate.source
            or fact.authority != matched_confirmation.authority
            or fact.confirmed_at != matched_confirmation.confirmed_at
        ):
            raise ValueError("handoff fact does not match confirmation and candidate evidence")

    supported_confirmation_ids = {
        confirmation.id
        for confirmation in artifact.confirmations
        if confirmation.disposition in supported_dispositions
    }
    if facts_by_confirmation.keys() != supported_confirmation_ids:
        raise ValueError("each supported confirmation requires exactly one confirmed fact")


def validate_handoff(artifact: HandoffArtifact) -> HandoffArtifact:
    _check_handoff(artifact)
    return artifact
