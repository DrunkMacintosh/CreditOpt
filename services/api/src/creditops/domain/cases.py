from pydantic import BaseModel, ConfigDict, Field

from creditops.domain.ids import ActorId, CaseId, FinancingRequestId


class CreditCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: CaseId
    version: int = Field(ge=1)
    assigned_officer_id: ActorId


class FinancingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: FinancingRequestId
    case_id: CaseId
    case_version: int = Field(ge=1)
    requested_amount: str = Field(min_length=1)
    purpose_vi: str = Field(min_length=1)
