import pytest

from creditops.domain.enums import DocumentStage, FactDisposition, GapStatus, TaskStatus
from creditops.domain.transitions import InvalidTransition, advance_document


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DocumentStage.REGISTERED, DocumentStage.SECURITY_VALIDATED),
        (DocumentStage.SECURITY_VALIDATED, DocumentStage.PARSED),
        (DocumentStage.PARSED, DocumentStage.CLASSIFIED),
        (DocumentStage.CLASSIFIED, DocumentStage.EXTRACTED),
        (DocumentStage.EXTRACTED, DocumentStage.INDEXED),
        (DocumentStage.INDEXED, DocumentStage.READY_FOR_OFFICER_REVIEW),
    ],
)
def test_document_advances_one_processing_stage(
    current: DocumentStage,
    target: DocumentStage,
) -> None:
    assert advance_document(current, target) is target


def test_worker_cannot_skip_processing_stage() -> None:
    with pytest.raises(InvalidTransition, match="REGISTERED.*EXTRACTED"):
        advance_document(DocumentStage.REGISTERED, DocumentStage.EXTRACTED)


def test_worker_cannot_move_document_backwards() -> None:
    with pytest.raises(InvalidTransition, match="PARSED.*SECURITY_VALIDATED"):
        advance_document(DocumentStage.PARSED, DocumentStage.SECURITY_VALIDATED)


def test_worker_cannot_repeat_a_completed_stage() -> None:
    with pytest.raises(InvalidTransition, match="PARSED.*PARSED"):
        advance_document(DocumentStage.PARSED, DocumentStage.PARSED)


def test_domain_status_values_are_explicit_wire_contracts() -> None:
    assert [stage.value for stage in DocumentStage] == [
        "REGISTERED",
        "SECURITY_VALIDATED",
        "PARSED",
        "CLASSIFIED",
        "EXTRACTED",
        "INDEXED",
        "READY_FOR_OFFICER_REVIEW",
    ]
    assert [status.value for status in TaskStatus] == [
        "PENDING",
        "RUNNING",
        "RETRY_WAIT",
        "SUCCEEDED",
        "FAILED_MANUAL_REVIEW",
        "SUPERSEDED",
    ]
    assert [disposition.value for disposition in FactDisposition] == [
        "ACCEPTED",
        "CORRECTED",
        "ABSENT",
        "UNREADABLE",
    ]
    assert [status.value for status in GapStatus] == [
        "PROVISIONAL",
        "FORMAL",
        "RESOLVED",
        "STALE",
    ]
