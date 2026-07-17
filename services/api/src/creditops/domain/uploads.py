from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from creditops.domain.ids import ActorId, CaseId, UploadIntentId


class UploadIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UploadIntentId
    case_id: CaseId
    assigned_officer_id: ActorId
    object_key: str = Field(min_length=1)
    accepted_content_type: str = Field(min_length=1)
    size_ceiling: int = Field(gt=0)
    expires_at: datetime
