from __future__ import annotations

from uuid import uuid4

import pytest

from creditops.application.stages.classify import classify_document
from creditops.application.stages.extract import ExtractionCandidate, validate_candidates
from creditops.application.stages.parse import ParsedDocument, ParsedRegion
from creditops.application.stages.security import validate_document_bytes


def _parsed() -> ParsedDocument:
    return ParsedDocument(
        document_version_id=uuid4(),
        content_type="application/pdf",
        extraction_method="test",
        regions=(
            ParsedRegion(page=1, text="Số tiền đề nghị: 500000000", x=0, y=0, width=1, height=0.1),
        ),
    )


def test_security_rejects_mismatched_content_type() -> None:
    with pytest.raises(ValueError, match="PDF"):
        validate_document_bytes(b"not-a-pdf", content_type="application/pdf")


def test_classifier_is_deterministic_and_does_not_make_a_credit_decision() -> None:
    result = classify_document(file_name="don_de_nghi_cap_tin_dung.pdf", parsed=_parsed())
    assert result.family == "CREDIT_REQUEST"
    assert result.confidence == 1.0
    assert "decision" not in result.model_dump_json().lower()


def test_grounded_candidates_must_reference_a_parsed_region() -> None:
    parsed = _parsed()
    candidate = ExtractionCandidate(
        field_key="requested_amount",
        proposed_value="500000000",
        confidence=0.92,
        page=1,
        x=0,
        y=0,
        width=0.2,
        height=0.1,
    )
    assert validate_candidates([candidate], parsed) == [candidate]
    outside = candidate.model_copy(update={"x": 0.8, "width": 0.3})
    with pytest.raises(ValueError, match="source region"):
        validate_candidates([outside], parsed)
