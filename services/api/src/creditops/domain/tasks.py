from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from creditops.domain.ids import CaseId, DocumentVersionId, TaskId


class TaskEnvelopeV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1"] = "1"
    task_id: TaskId
    case_id: CaseId
    case_version: int = Field(ge=1)
    document_version_id: DocumentVersionId
