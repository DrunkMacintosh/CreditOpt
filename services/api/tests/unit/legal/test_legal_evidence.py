"""Deterministic collateral checklist + ownership cross-check tests.

All customer data is synthetic and created solely for demonstration.  The
fixture case belongs to the invented SME "Cong ty TNHH San Xuat Gia Dat Demo".
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from creditops.application.legal.evidence import (
    check_ownership_consistency,
    evaluate_collateral_checklist,
)
from creditops.application.ports.legal import EvidenceFact, LegalEvidenceView
from creditops.domain.legal import CollateralDocumentStatus, GapBlockingLevel

NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
CASE_ID = uuid4()


def make_view(*facts: EvidenceFact) -> LegalEvidenceView:
    return LegalEvidenceView(
        case_id=CASE_ID, case_version=1, built_at=NOW, confirmed_facts=tuple(facts)
    )


def fact(field_key: str, value: object) -> EvidenceFact:
    return EvidenceFact(
        confirmed_fact_id=uuid4(),
        field_key=field_key,
        value=value,  # type: ignore[arg-type]
        document_version_id=uuid4(),
    )


class TestMissingDocumentsCreateBlockingGaps:
    def test_entirely_unrecorded_document_creates_a_gap_not_a_missing_item(self) -> None:
        view = make_view()
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        assert result.items == ()
        assert len(result.gaps) == 3
        assert {gap.blocking_level for gap in result.gaps} == {
            GapBlockingLevel.BLOCKING,
            GapBlockingLevel.CONDITIONAL,
        }

    def test_explicitly_missing_document_creates_a_blocking_gap_and_item(self) -> None:
        view = make_view(
            fact("collateral.documents.giay_chung_nhan_qsdd.status", "MISSING")
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "giay_chung_nhan_qsdd"
        )
        assert item.status == CollateralDocumentStatus.MISSING
        assert len(item.citations) == 1
        gap = next(
            g for g in result.gaps if "Thiếu tài liệu" in g.missing_information_vi
        )
        assert gap.blocking_level == GapBlockingLevel.BLOCKING


class TestExpiredDocumentsCreateGaps:
    def test_expired_title_deed_is_blocking(self) -> None:
        view = make_view(
            fact("collateral.documents.giay_chung_nhan_qsdd.status", "PRESENT"),
            fact(
                "collateral.documents.giay_chung_nhan_qsdd.expiry_date", "2020-01-01"
            ),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "giay_chung_nhan_qsdd"
        )
        assert item.status == CollateralDocumentStatus.EXPIRED
        assert item.expiry_date == date(2020, 1, 1)
        gap = next(g for g in result.gaps if "đã hết hạn" in g.missing_information_vi)
        assert gap.blocking_level == GapBlockingLevel.BLOCKING

    def test_expired_valuation_report_is_conditional(self) -> None:
        view = make_view(
            fact("collateral.documents.bien_ban_dinh_gia.status", "PRESENT"),
            fact("collateral.documents.bien_ban_dinh_gia.expiry_date", "2020-01-01"),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "bien_ban_dinh_gia"
        )
        assert item.status == CollateralDocumentStatus.EXPIRED
        gap = next(g for g in result.gaps if "đã hết hạn" in g.missing_information_vi)
        assert gap.blocking_level == GapBlockingLevel.CONDITIONAL

    def test_present_and_not_expired_document_has_no_gap_for_it(self) -> None:
        view = make_view(
            fact("collateral.documents.giay_chung_nhan_qsdd.status", "PRESENT"),
            fact(
                "collateral.documents.giay_chung_nhan_qsdd.expiry_date", "2099-01-01"
            ),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "giay_chung_nhan_qsdd"
        )
        assert item.status == CollateralDocumentStatus.PRESENT
        assert not any(
            "giay_chung_nhan_qsdd" in gap.missing_information_vi
            or "hết hạn" in gap.missing_information_vi
            for gap in result.gaps
        )

    def test_present_without_expiry_fact_creates_clarification_gap(self) -> None:
        view = make_view(
            fact("collateral.documents.giay_chung_nhan_qsdd.status", "PRESENT"),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "giay_chung_nhan_qsdd"
        )
        assert item.status == CollateralDocumentStatus.PRESENT
        assert item.expiry_date is None
        gap = next(
            g for g in result.gaps if "ngày hết hạn" in g.missing_information_vi
        )
        assert gap.blocking_level == GapBlockingLevel.CLARIFICATION

    def test_document_not_requiring_expiry_check_is_present_without_expiry_gap(
        self,
    ) -> None:
        view = make_view(
            fact("collateral.documents.hop_dong_the_chap.status", "PRESENT"),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        item = next(
            i for i in result.items if i.document_type_key == "hop_dong_the_chap"
        )
        assert item.status == CollateralDocumentStatus.PRESENT
        assert not any(
            "hop_dong_the_chap" in gap.missing_information_vi for gap in result.gaps
        )

    def test_invalid_status_value_creates_clarification_gap(self) -> None:
        view = make_view(
            fact("collateral.documents.giay_chung_nhan_qsdd.status", "UNKNOWN_VALUE"),
        )
        result = evaluate_collateral_checklist(view, as_of=date(2026, 7, 18))
        assert result.items == ()
        gap = result.gaps[0]
        assert gap.blocking_level == GapBlockingLevel.CLARIFICATION


class TestOwnershipCrossCheck:
    def test_matching_owner_names_produce_no_inconsistency(self) -> None:
        view = make_view(
            fact("legal.entity.registered_name_vi", "Cong ty TNHH ABC"),
            fact("collateral.asset.owner_name_vi", "cong ty tnhh abc"),
        )
        assert check_ownership_consistency(view) == ()

    def test_mismatched_owner_names_produce_a_deterministic_inconsistency(self) -> None:
        view = make_view(
            fact("legal.entity.registered_name_vi", "Cong ty TNHH ABC"),
            fact("collateral.asset.owner_name_vi", "Nguyen Van A"),
        )
        result = check_ownership_consistency(view)
        assert len(result) == 1
        assert result[0].detected_by == "DETERMINISTIC_CROSS_CHECK"
        assert len(result[0].citations) == 2

    def test_missing_either_fact_produces_no_inconsistency(self) -> None:
        view = make_view(fact("legal.entity.registered_name_vi", "Cong ty TNHH ABC"))
        assert check_ownership_consistency(view) == ()
