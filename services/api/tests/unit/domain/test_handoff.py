from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from creditops.domain.cases import CreditCase, FinancingRequest
from creditops.domain.documents import Document, DocumentVersion
from creditops.domain.enums import FactDisposition
from creditops.domain.evidence import (
    CandidateFact,
    ConfirmedFact,
    FactConfirmation,
    PageRegion,
)
from creditops.domain.gaps import EvidenceGap
from creditops.domain.handoffs import HandoffArtifact, validate_handoff
from creditops.domain.tasks import TaskEnvelopeV1
from creditops.domain.uploads import UploadIntent


def confirmed_fact() -> ConfirmedFact:
    candidate = CandidateFact(
        id=uuid4(),
        document_version_id=uuid4(),
        field_key="requested_amount",
        proposed_value="5000000000",
        confidence=0.91,
        source=PageRegion(page=1, x=0.1, y=0.2, width=0.3, height=0.04),
    )
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=candidate.id,
        disposition=FactDisposition.ACCEPTED,
        actor_id=uuid4(),
    )
    return ConfirmedFact.from_confirmation(
        id=uuid4(),
        candidate=candidate,
        confirmation=confirmation,
    )


def handoff_artifact(
    *,
    open_candidate_ids: tuple[UUID, ...] = (),
    unsupported_fact_ids: tuple[UUID, ...] = (),
) -> HandoffArtifact:
    return HandoffArtifact(
        id=uuid4(),
        case_id=uuid4(),
        case_version=7,
        confirmed_facts=(confirmed_fact(),),
        open_candidate_ids=open_candidate_ids,
        unsupported_fact_ids=unsupported_fact_ids,
    )


def test_valid_handoff_is_bound_to_an_exact_case_version() -> None:
    artifact = handoff_artifact()

    assert validate_handoff(artifact) is artifact
    assert artifact.case_version == 7
    assert artifact.state == "READY_FOR_SPECIALIST_REVIEW"
    assert "credit_decision" not in artifact.model_dump()


def test_handoff_rejects_open_candidates() -> None:
    with pytest.raises(ValidationError, match="open candidates"):
        handoff_artifact(open_candidate_ids=(uuid4(),))


def test_handoff_rejects_unsupported_facts() -> None:
    with pytest.raises(ValidationError, match="unsupported facts"):
        handoff_artifact(unsupported_fact_ids=(uuid4(),))


def test_handoff_rejects_any_credit_decision_field() -> None:
    with pytest.raises(ValidationError, match="credit_decision"):
        HandoffArtifact(
            id=uuid4(),
            case_id=uuid4(),
            case_version=7,
            confirmed_facts=(confirmed_fact(),),
            credit_decision="APPROVE",
        )


def test_validate_handoff_rechecks_models_built_without_validation() -> None:
    artifact = HandoffArtifact.model_construct(
        id=uuid4(),
        case_id=uuid4(),
        case_version=7,
        state="READY_FOR_SPECIALIST_REVIEW",
        confirmed_facts=(confirmed_fact(),),
        open_candidate_ids=(uuid4(),),
        unsupported_fact_ids=(),
        conflict_ids=(),
        gap_ids=(),
        stale=False,
    )

    with pytest.raises(ValueError, match="open candidates"):
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
