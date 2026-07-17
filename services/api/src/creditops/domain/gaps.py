from pydantic import BaseModel, ConfigDict, Field

from creditops.domain.enums import GapStatus
from creditops.domain.ids import (
    CaseId,
    EvidenceGapId,
    EvidenceId,
    PolicyCitationId,
    TaskId,
)


class EvidenceGap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EvidenceGapId
    case_id: CaseId
    case_version: int = Field(ge=1)
    status: GapStatus
    issue_vi: str = Field(min_length=1)
    existing_evidence_ids: tuple[EvidenceId, ...]
    missing_information_vi: str = Field(min_length=1)
    affected_task_ids: tuple[TaskId, ...] = Field(min_length=1)
    suggested_evidence_vi: tuple[str, ...] = ()
    policy_citation_ids: tuple[PolicyCitationId, ...] = ()
