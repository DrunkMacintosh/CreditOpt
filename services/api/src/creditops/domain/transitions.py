from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from creditops.domain.enums import DocumentStage


class InvalidTransition(ValueError):
    pass


_ALLOWED_DOCUMENT_TRANSITIONS: Final[Mapping[DocumentStage, DocumentStage]] = (
    MappingProxyType(
        {
            DocumentStage.REGISTERED: DocumentStage.SECURITY_VALIDATED,
            DocumentStage.SECURITY_VALIDATED: DocumentStage.PARSED,
            DocumentStage.PARSED: DocumentStage.CLASSIFIED,
            DocumentStage.CLASSIFIED: DocumentStage.EXTRACTED,
            DocumentStage.EXTRACTED: DocumentStage.INDEXED,
            DocumentStage.INDEXED: DocumentStage.READY_FOR_OFFICER_REVIEW,
        }
    )
)


def advance_document(current: DocumentStage, target: DocumentStage) -> DocumentStage:
    if _ALLOWED_DOCUMENT_TRANSITIONS.get(current) is not target:
        raise InvalidTransition(
            f"invalid document transition: {current.value} -> {target.value}"
        )
    return target
