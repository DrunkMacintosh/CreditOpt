from uuid import uuid4

import pytest
from pydantic import ValidationError

from creditops.domain.enums import FactDisposition
from creditops.domain.evidence import (
    CandidateFact,
    ConfirmedFact,
    FactConfirmation,
    PageRegion,
)


def candidate_fact() -> CandidateFact:
    return CandidateFact(
        id=uuid4(),
        document_version_id=uuid4(),
        field_key="requested_amount",
        proposed_value="5000000000",
        confidence=0.91,
        source=PageRegion(page=1, x=0.1, y=0.2, width=0.3, height=0.04),
    )


def test_candidate_requires_normalized_addressable_source() -> None:
    candidate = candidate_fact()

    assert candidate.source.page == 1


def test_region_outside_page_is_rejected() -> None:
    with pytest.raises(ValidationError, match="region exceeds normalized page"):
        PageRegion(page=1, x=0.9, y=0.2, width=0.2, height=0.1)


def test_candidate_without_source_region_is_rejected() -> None:
    with pytest.raises(ValidationError, match="source"):
        CandidateFact(
            id=uuid4(),
            document_version_id=uuid4(),
            field_key="requested_amount",
            proposed_value="5000000000",
            confidence=0.91,
        )


def test_candidate_rejects_unsupported_structured_value() -> None:
    with pytest.raises(ValidationError, match="proposed_value"):
        CandidateFact(
            id=uuid4(),
            document_version_id=uuid4(),
            field_key="requested_amount",
            proposed_value=["not", "an", "evidence scalar"],
            confidence=0.91,
            source=PageRegion(page=1, x=0.1, y=0.2, width=0.3, height=0.04),
        )


def test_confirmation_rejects_open_disposition() -> None:
    with pytest.raises(ValidationError, match="OPEN"):
        FactConfirmation(
            id=uuid4(),
            candidate_id=uuid4(),
            disposition="OPEN",
            actor_id=uuid4(),
        )


def test_correction_requires_a_replacement_value() -> None:
    with pytest.raises(ValidationError, match="corrected_value"):
        FactConfirmation(
            id=uuid4(),
            candidate_id=uuid4(),
            disposition=FactDisposition.CORRECTED,
            actor_id=uuid4(),
        )


def test_only_supported_confirmation_creates_confirmed_fact() -> None:
    candidate = candidate_fact()
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=candidate.id,
        disposition=FactDisposition.ACCEPTED,
        actor_id=uuid4(),
    )

    fact = ConfirmedFact.from_confirmation(
        id=uuid4(),
        candidate=candidate,
        confirmation=confirmation,
    )

    assert fact.value == candidate.proposed_value
    assert fact.candidate_value == candidate.proposed_value
    assert fact.source == candidate.source
    assert fact.confirmed_by == confirmation.actor_id


def test_correction_preserves_candidate_value_and_source() -> None:
    candidate = candidate_fact()
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=candidate.id,
        disposition=FactDisposition.CORRECTED,
        actor_id=uuid4(),
        corrected_value="4800000000",
    )

    fact = ConfirmedFact.from_confirmation(
        id=uuid4(),
        candidate=candidate,
        confirmation=confirmation,
    )

    assert fact.value == "4800000000"
    assert fact.candidate_value == "5000000000"
    assert fact.source == candidate.source


@pytest.mark.parametrize(
    "disposition",
    [FactDisposition.ABSENT, FactDisposition.UNREADABLE],
)
def test_unsupported_disposition_cannot_create_confirmed_fact(
    disposition: FactDisposition,
) -> None:
    candidate = candidate_fact()
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=candidate.id,
        disposition=disposition,
        actor_id=uuid4(),
    )

    with pytest.raises(ValueError, match="does not support a confirmed fact"):
        ConfirmedFact.from_confirmation(
            id=uuid4(),
            candidate=candidate,
            confirmation=confirmation,
        )


def test_confirmation_must_reference_the_candidate() -> None:
    candidate = candidate_fact()
    confirmation = FactConfirmation(
        id=uuid4(),
        candidate_id=uuid4(),
        disposition=FactDisposition.ACCEPTED,
        actor_id=uuid4(),
    )

    with pytest.raises(ValueError, match="candidate"):
        ConfirmedFact.from_confirmation(
            id=uuid4(),
            candidate=candidate,
            confirmation=confirmation,
        )


def test_evidence_models_are_immutable() -> None:
    candidate = candidate_fact()

    with pytest.raises(ValidationError, match="frozen"):
        candidate.field_key = "mutated"
