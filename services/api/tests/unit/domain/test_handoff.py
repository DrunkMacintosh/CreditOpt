from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from creditops.domain.cases import CreditCase, FinancingRequest
from creditops.domain.documents import Document, DocumentVersion
from creditops.domain.enums import FactDisposition
from creditops.domain.evidence import (
    CandidateFact,
    ConfirmationAuthority,
    ConfirmedFact,
    FactConfirmation,
    PageRegion,
)
from creditops.domain.gaps import EvidenceGap
from creditops.domain.handoffs import HandoffArtifact, validate_handoff
from creditops.domain.tasks import TaskEnvelopeV1
from creditops.domain.uploads import UploadIntent

GRANTED_AT = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
CONFIRMED_AT = GRANTED_AT + timedelta(minutes=5)


def evidence_bundle(
    *,
    case_id: UUID,
    case_version: int = 7,
    disposition: FactDisposition = FactDisposition.ACCEPTED,
    corrected_value: str | None = None,
) -> tuple[CandidateFact, FactConfirmation, ConfirmedFact | None]:
    officer_id = uuid4()
    candidate = CandidateFact(
        id=uuid4(),
        case_id=case_id,
        case_version=case_version,
        document_version_id=uuid4(),
        field_key="requested_amount",
        proposed_value="5000000000",
        confidence=0.91,
        source=PageRegion(page=1, x=0.1, y=0.2, width=0.3, height=0.04),
    )
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=candidate.id,
        disposition=disposition,
        authority=ConfirmationAuthority(
            case_id=case_id,
            case_version=case_version,
            actor_id=officer_id,
            assigned_officer_id=officer_id,
            granted_at=GRANTED_AT,
            source="CASE_ASSIGNMENT",
        ),
        confirmed_at=CONFIRMED_AT,
        corrected_value=corrected_value,
    )
    fact = None
    if disposition in {FactDisposition.ACCEPTED, FactDisposition.CORRECTED}:
        fact = ConfirmedFact.from_confirmation(
            id=uuid4(),
            candidate=candidate,
            confirmation=confirmation,
        )
    return candidate, confirmation, fact


def handoff_artifact() -> HandoffArtifact:
    case_id = uuid4()
    candidate, confirmation, fact = evidence_bundle(case_id=case_id)
    assert fact is not None
    return HandoffArtifact(
        id=uuid4(),
        case_id=case_id,
        case_version=7,
        candidates=(candidate,),
        confirmations=(confirmation,),
        confirmed_facts=(fact,),
    )


def test_valid_handoff_is_bound_to_an_exact_case_version() -> None:
    artifact = handoff_artifact()

    assert validate_handoff(artifact) is artifact
    assert artifact.case_version == 7
    assert artifact.state == "READY_FOR_SPECIALIST_REVIEW"
    assert "credit_decision" not in artifact.model_dump()


def test_handoff_rejects_candidate_without_disposition() -> None:
    case_id = uuid4()
    first_candidate, first_confirmation, first_fact = evidence_bundle(case_id=case_id)
    second_candidate, _, _ = evidence_bundle(case_id=case_id)
    assert first_fact is not None

    with pytest.raises(ValidationError, match="missing confirmation"):
        HandoffArtifact(
            id=uuid4(),
            case_id=case_id,
            case_version=7,
            candidates=(first_candidate, second_candidate),
            confirmations=(first_confirmation,),
            confirmed_facts=(first_fact,),
        )


def test_handoff_rejects_duplicate_disposition_for_candidate() -> None:
    case_id = uuid4()
    candidate, confirmation, fact = evidence_bundle(case_id=case_id)
    assert fact is not None
    duplicate = confirmation.model_copy(update={"id": uuid4()})

    with pytest.raises(ValidationError, match="exactly one disposition"):
        HandoffArtifact(
            id=uuid4(),
            case_id=case_id,
            case_version=7,
            candidates=(candidate,),
            confirmations=(confirmation, duplicate),
            confirmed_facts=(fact,),
        )


def test_handoff_rejects_supported_confirmation_without_fact() -> None:
    case_id = uuid4()
    candidate, confirmation, _ = evidence_bundle(case_id=case_id)

    with pytest.raises(ValidationError, match="confirmed fact"):
        HandoffArtifact(
            id=uuid4(),
            case_id=case_id,
            case_version=7,
            candidates=(candidate,),
            confirmations=(confirmation,),
            confirmed_facts=(),
        )


def test_handoff_rejects_cross_case_fact() -> None:
    artifact_case_id = uuid4()
    candidate, confirmation, fact = evidence_bundle(case_id=artifact_case_id)
    _, _, cross_case_fact = evidence_bundle(case_id=uuid4())
    assert fact is not None
    assert cross_case_fact is not None

    with pytest.raises(ValidationError, match="case/version"):
        HandoffArtifact(
            id=uuid4(),
            case_id=artifact_case_id,
            case_version=7,
            candidates=(candidate,),
            confirmations=(confirmation,),
            confirmed_facts=(cross_case_fact,),
        )


def test_handoff_rejects_fact_that_does_not_match_confirmation() -> None:
    case_id = uuid4()
    candidate, confirmation, fact = evidence_bundle(case_id=case_id)
    assert fact is not None
    unsupported_fact = fact.model_copy(update={"value": "unsupported"})

    with pytest.raises(ValidationError, match="does not match confirmation"):
        HandoffArtifact(
            id=uuid4(),
            case_id=case_id,
            case_version=7,
            candidates=(candidate,),
            confirmations=(confirmation,),
            confirmed_facts=(unsupported_fact,),
        )


def test_handoff_rejects_fact_without_source_region() -> None:
    case_id = uuid4()
    candidate, confirmation, fact = evidence_bundle(case_id=case_id)
    assert fact is not None
    unsupported_fact = fact.model_copy(update={"source": None})

    with pytest.raises(ValidationError, match="source region"):
        HandoffArtifact(
            id=uuid4(),
            case_id=case_id,
            case_version=7,
            candidates=(candidate,),
            confirmations=(confirmation,),
            confirmed_facts=(unsupported_fact,),
        )


def test_handoff_rejects_any_credit_decision_field() -> None:
    artifact = handoff_artifact()

    with pytest.raises(ValidationError, match="credit_decision"):
        HandoffArtifact(
            **artifact.model_dump(),
            credit_decision="APPROVE",
        )


def test_validate_handoff_rechecks_models_built_without_validation() -> None:
    case_id = uuid4()
    candidate, _, _ = evidence_bundle(case_id=case_id)
    artifact = HandoffArtifact.model_construct(
        id=uuid4(),
        case_id=case_id,
        case_version=7,
        state="READY_FOR_SPECIALIST_REVIEW",
        candidates=(candidate,),
        confirmations=(),
        confirmed_facts=(),
        conflict_ids=(),
        gap_ids=(),
        stale=False,
    )

    with pytest.raises(ValueError, match="missing confirmation"):
        validate_handoff(artifact)


def test_handoff_is_immutable() -> None:
    artifact = handoff_artifact()

    with pytest.raises(ValidationError, match="frozen"):
        artifact.case_version = 8


def test_case_and_financing_request_are_immutable_versioned_records() -> None:
    case_id = uuid4()
    case = CreditCase(id=case_id, version=1, assigned_officer_id=uuid4())
    request = FinancingRequest(
        id=uuid4(),
        case_id=case_id,
        case_version=1,
        requested_amount="5000000000",
        purpose_vi="Bổ sung vốn lưu động",
    )

    assert request.case_version == case.version
    with pytest.raises(ValidationError, match="frozen"):
        case.version = 2


def test_upload_intent_binds_upload_constraints_to_case_and_officer() -> None:
    case_id = uuid4()
    officer_id = uuid4()
    intent = UploadIntent(
        id=uuid4(),
        case_id=case_id,
        assigned_officer_id=officer_id,
        object_key=f"incoming/{case_id}/{uuid4()}",
        accepted_content_type="application/pdf",
        size_ceiling=10_000_000,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    assert intent.case_id == case_id
    assert intent.assigned_officer_id == officer_id


def test_document_version_has_one_explicit_processing_stage() -> None:
    document = Document(id=uuid4(), case_id=uuid4())
    version = DocumentVersion(
        id=uuid4(),
        document_id=document.id,
        version=1,
        stage="REGISTERED",
    )

    assert version.stage.value == "REGISTERED"


def test_task_envelope_is_versioned_and_contains_only_durable_identifiers() -> None:
    envelope = TaskEnvelopeV1(
        task_id=uuid4(),
        case_id=uuid4(),
        case_version=3,
        document_version_id=uuid4(),
    )

    assert envelope.schema_version == "1"
    assert "document_body" not in envelope.model_dump()


def test_gap_records_considered_evidence_missing_information_and_affected_work() -> None:
    gap = EvidenceGap(
        id=uuid4(),
        case_id=uuid4(),
        case_version=2,
        status="PROVISIONAL",
        issue_vi="Thiếu bằng chứng cho mục đích sử dụng vốn",
        existing_evidence_ids=(uuid4(),),
        missing_information_vi="Chứng từ chứng minh mục đích sử dụng vốn",
        affected_task_ids=(uuid4(),),
        suggested_evidence_vi=("Hợp đồng mua hàng",),
    )

    assert gap.existing_evidence_ids
    assert gap.missing_information_vi
    assert gap.affected_task_ids
