from pydantic import BaseModel, ConfigDict, Field

from creditops.domain.enums import DocumentStage
from creditops.domain.ids import CaseId, DocumentId, DocumentVersionId


class Document(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: DocumentId
    case_id: CaseId


class DocumentVersion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: DocumentVersionId
    document_id: DocumentId
    version: int = Field(ge=1)
    stage: DocumentStage
