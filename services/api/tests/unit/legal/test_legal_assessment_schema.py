"""Schema tests for the LegalComplianceAssessment contract.

All customer data, policies, documents, and banking-system responses in this
project are synthetic and created solely for demonstration.  The fixture case
belongs to the invented SME "Cong ty TNHH Xay Dung Phuong Nam Demo".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from creditops.domain.legal import (
    FORBIDDEN_LEGAL_FIELD_NAMES,
    AssessmentSection,
    CollateralDocumentItem,
    CollateralDocumentStatus,
    CollateralReviewSection,
    ConfidenceLevel,
    ConfirmedFactCitation,
    ControlledCheckCitation,
    ControlledCheckInterpretation,
    ControlledCheckResultRecord,
    ControlledCheckStatus,
    ControlledCheckType,
    ExceptionCategory,
    ExceptionItem,
    Finding,
    LegalAssessmentProvenance,
    LegalComplianceAssessment,
    OwnershipConsistencySection,
    OwnershipInconsistencyItem,
    PolicyCitation,
    PolicyFinding,
    PolicyHitRecord,
)

NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
FACT_ID = uuid4()
FACT_ID_2 = uuid4()
INVOCATION_ID = uuid4()

POLICY_HIT = PolicyHitRecord(
    corpus_id="SHB-SYNTHETIC-POLICY-CORPUS",
    corpus_version="v1",
    document_id="tai_san_bao_dam",
    clause_id="TSBD-01",
    quoted_text_vi="Hồ sơ tài sản bảo đảm phải có giấy chứng nhận hợp lệ.",
)

CHECK_RESULT = ControlledCheckResultRecord(
    invocation_id=INVOCATION_ID,
    check_type=ControlledCheckType.KYC,
    provider_id="synthetic-mock-compliance-provider",
    tool_name="synthetic-kyc-mock",
    tool_version="mock-v1",
    subject_type="ENTITY",
    subject_ref_vi="Cong ty TNHH Xay Dung Phuong Nam Demo",
    status=ControlledCheckStatus.CLEAR,
    result_summary_vi="Khong phat hien trong du lieu mo phong.",
    invoked_at=NOW,
)


def fact_citation(fact_id: Any = FACT_ID) -> ConfirmedFactCitation:
    return ConfirmedFactCitation(confirmed_fact_id=fact_id)


def finding(text: str = "Doanh nghiep dang hoat dong hop le.") -> Finding:
    return Finding(
        statement_vi=text,
        citations=(fact_citation(),),
        confidence=ConfidenceLevel.MEDIUM,
    )


def provenance() -> LegalAssessmentProvenance:
    return LegalAssessmentProvenance(
        case_id=uuid4(),
        case_version=1,
        execution_id=uuid4(),
        task_id=uuid4(),
        prompt_version="legal-prompt-v1",
        model_id="synthetic-model",
        endpoint_id="synthetic-endpoint",
        evidence_view_built_at=NOW,
        created_at=NOW,
    )


def assessment(**overrides: Any) -> LegalComplianceAssessment:
    base: dict[str, Any] = {
        "id": uuid4(),
        "provenance": provenance(),
        "legal_entity_review": AssessmentSection(findings=(finding(),)),
        "authority_signatory_review": AssessmentSection(findings=(finding(),)),
        "ownership_consistency": OwnershipConsistencySection(findings=(finding(),)),
        "collateral_review": CollateralReviewSection(
            ownership_evidence_findings=(finding(),)
        ),
    }
    base.update(overrides)
    return LegalComplianceAssessment(**base)


class TestCitationsRequired:
    def test_valid_assessment_builds(self) -> None:
        built = assessment()
        assert built.provenance.agent_role == "LEGAL_COMPLIANCE_COLLATERAL"

    def test_finding_with_empty_citations_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                statement_vi="Ket luan khong co can cu.",
                citations=(),
                confidence=ConfidenceLevel.LOW,
            )

    def test_policy_finding_requires_policy_citation(self) -> None:
        with pytest.raises(ValidationError):
            PolicyFinding(
                possible_issue_vi="Co the ap dung mot dieu khoan.",
                citations=(),
                confidence=ConfidenceLevel.LOW,
            )

    def test_exception_requires_uncertainty(self) -> None:
        with pytest.raises(ValidationError):
            ExceptionItem(
                category=ExceptionCategory.LEGAL,
                possible_issue_vi="Co the co bat thuong.",
                citations=(fact_citation(),),
                confidence=ConfidenceLevel.LOW,
                uncertainty_vi="",
            )


class TestPolicyCitationGrounding:
    def test_policy_finding_with_grounded_citation_builds(self) -> None:
        built = assessment(
            policy_review=(
                PolicyFinding(
                    possible_issue_vi="Co the ap dung dieu khoan tai san bao dam.",
                    citations=(
                        PolicyCitation(
                            corpus_id=POLICY_HIT.corpus_id,
                            corpus_version=POLICY_HIT.corpus_version,
                            document_id=POLICY_HIT.document_id,
                            clause_id=POLICY_HIT.clause_id,
                            quoted_text_vi=POLICY_HIT.quoted_text_vi,
                        ),
                    ),
                    confidence=ConfidenceLevel.MEDIUM,
                ),
            ),
            policy_hits=(POLICY_HIT,),
        )
        assert len(built.policy_review) == 1

    def test_policy_citation_outside_offered_hits_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not resolve"):
            assessment(
                policy_review=(
                    PolicyFinding(
                        possible_issue_vi="Trich dan ngoai pham vi.",
                        citations=(
                            PolicyCitation(
                                corpus_id=POLICY_HIT.corpus_id,
                                corpus_version=POLICY_HIT.corpus_version,
                                document_id=POLICY_HIT.document_id,
                                clause_id="TSBD-99-KHONG-TON-TAI",
                                quoted_text_vi="Dieu khoan bia.",
                            ),
                        ),
                        confidence=ConfidenceLevel.LOW,
                    ),
                ),
                # No policy_hits recorded: nothing grounds this citation.
            )

    def test_policy_citation_with_altered_quote_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not resolve"):
            assessment(
                policy_review=(
                    PolicyFinding(
                        possible_issue_vi="Trich dan bi sua doi.",
                        citations=(
                            PolicyCitation(
                                corpus_id=POLICY_HIT.corpus_id,
                                corpus_version=POLICY_HIT.corpus_version,
                                document_id=POLICY_HIT.document_id,
                                clause_id=POLICY_HIT.clause_id,
                                quoted_text_vi="Van ban da bi thay doi noi dung.",
                            ),
                        ),
                        confidence=ConfidenceLevel.LOW,
                    ),
                ),
                policy_hits=(POLICY_HIT,),
            )


class TestControlledCheckGrounding:
    def test_interpretation_referencing_known_invocation_builds(self) -> None:
        built = assessment(
            controlled_check_interpretations=(
                ControlledCheckInterpretation(
                    invocation_id=INVOCATION_ID,
                    statement_vi="Khong phat hien canh bao.",
                    confidence=ConfidenceLevel.HIGH,
                ),
            ),
            controlled_check_results=(CHECK_RESULT,),
        )
        assert built.controlled_check_interpretations[0].invocation_id == INVOCATION_ID

    def test_interpretation_referencing_fabricated_invocation_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            assessment(
                controlled_check_interpretations=(
                    ControlledCheckInterpretation(
                        invocation_id=uuid4(),
                        statement_vi="Ket qua bia.",
                        confidence=ConfidenceLevel.LOW,
                    ),
                ),
                controlled_check_results=(CHECK_RESULT,),
            )

    def test_controlled_check_citation_referencing_fabricated_id_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            assessment(
                exceptions=(
                    ExceptionItem(
                        category=ExceptionCategory.POLICY,
                        possible_issue_vi="Co the co ngoai le.",
                        citations=(ControlledCheckCitation(invocation_id=uuid4()),),
                        confidence=ConfidenceLevel.LOW,
                        uncertainty_vi="Chua ro.",
                    ),
                ),
                controlled_check_results=(CHECK_RESULT,),
            )


class TestUncertaintyAndConfidenceSurvive:
    def test_uncertainty_and_confidence_round_trip_through_serialization(self) -> None:
        built = assessment(
            exceptions=(
                ExceptionItem(
                    category=ExceptionCategory.COLLATERAL,
                    possible_issue_vi="Co the thieu van ban dong so huu.",
                    citations=(fact_citation(),),
                    confidence=ConfidenceLevel.LOW,
                    uncertainty_vi="Chua xac dinh duoc tinh trang dong so huu.",
                ),
            )
        )
        dumped = json.loads(json.dumps(built.model_dump(mode="json")))
        restored = LegalComplianceAssessment.model_validate(dumped)
        assert restored.exceptions[0].confidence == ConfidenceLevel.LOW
        assert (
            restored.exceptions[0].uncertainty_vi
            == "Chua xac dinh duoc tinh trang dong so huu."
        )


class TestUpgradingPossibleIssueFailsSchema:
    """An LLM response upgrading a potential issue to a determination-like
    field must fail schema validation — not merely be ignored."""

    def test_extra_legal_determination_field_is_rejected(self) -> None:
        for forbidden in (
            "legal_conclusion",
            "wrongdoing",
            "violation_confirmed",
            "collateral_value",
        ):
            with pytest.raises(ValidationError):
                LegalComplianceAssessment.model_validate(
                    {**assessment().model_dump(), forbidden: "CONFIRMED"}
                )

    def test_exception_item_rejects_a_determination_field(self) -> None:
        with pytest.raises(ValidationError):
            ExceptionItem.model_validate(
                {
                    "category": "LEGAL",
                    "possible_issue_vi": "Co the co vi pham.",
                    "citations": [
                        {"kind": "CONFIRMED_FACT", "confirmed_fact_id": str(FACT_ID)}
                    ],
                    "confidence": "LOW",
                    "uncertainty_vi": "Chua ro.",
                    "legal_conclusion": "VI_PHAM",
                }
            )

    def test_schema_has_no_forbidden_field_names(self) -> None:
        schema = json.dumps(LegalComplianceAssessment.model_json_schema())
        properties: set[str] = set()

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "properties" and isinstance(value, dict):
                        properties.update(value.keys())
                    collect(value)
            elif isinstance(node, list):
                for item in node:
                    collect(item)

        collect(json.loads(schema))
        normalized = {
            "".join(char for char in name.casefold() if char.isalnum())
            for name in properties
        }
        assert not normalized & FORBIDDEN_LEGAL_FIELD_NAMES

    def test_collateral_value_field_is_specifically_forbidden(self) -> None:
        assert "collateralvalue" in FORBIDDEN_LEGAL_FIELD_NAMES
        assert "appraisalvalue" in FORBIDDEN_LEGAL_FIELD_NAMES
        assert "wrongdoing" in FORBIDDEN_LEGAL_FIELD_NAMES
        assert "violationconfirmed" in FORBIDDEN_LEGAL_FIELD_NAMES


class TestImmutabilityAndCollateral:
    def test_assessment_is_frozen(self) -> None:
        built = assessment()
        with pytest.raises(ValidationError):
            built.id = uuid4()  # type: ignore[misc]

    def test_collateral_document_item_carries_status_and_citation(self) -> None:
        item = CollateralDocumentItem(
            document_type_key="giay_chung_nhan_qsdd",
            label_vi="Giay chung nhan quyen su dung dat",
            status=CollateralDocumentStatus.MISSING,
            citations=(fact_citation(),),
        )
        built = assessment(
            collateral_review=CollateralReviewSection(
                document_items=(item,),
                ownership_evidence_findings=(finding(),),
            )
        )
        assert built.collateral_review.document_items[0].status == (
            CollateralDocumentStatus.MISSING
        )

    def test_ownership_inconsistency_requires_two_citations(self) -> None:
        with pytest.raises(ValidationError):
            assessment(
                ownership_consistency=OwnershipConsistencySection(
                    findings=(finding(),),
                    inconsistencies=(
                        OwnershipInconsistencyItem(
                            description_vi="Khong khop ten so huu.",
                            citations=(fact_citation(),),
                        ),
                    ),
                )
            )

    def test_ownership_inconsistency_with_two_citations_builds(self) -> None:
        built = assessment(
            ownership_consistency=OwnershipConsistencySection(
                findings=(finding(),),
                inconsistencies=(
                    OwnershipInconsistencyItem(
                        description_vi="Khong khop ten so huu.",
                        citations=(
                            fact_citation(FACT_ID),
                            fact_citation(FACT_ID_2),
                        ),
                    ),
                ),
            )
        )
        assert len(built.ownership_consistency.inconsistencies) == 1
