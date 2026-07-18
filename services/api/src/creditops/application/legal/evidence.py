"""Scoped evidence view -> deterministic legal/collateral pre-analysis.

Pure functions only, run BEFORE inference — mirrors
``application/underwriting/evidence.py``'s calculator-suite pattern.  The
collateral checklist operationalizes the synthetic "tai_san_bao_dam" policy
document's document-completeness clauses (TSBD-01..03); the requirement list
itself is deterministic code, not LLM-derived, exactly like the maker's
calculators are deterministic formulas the LLM only cites.  ASSUMPTION: the
field-key taxonomy below is SYNTHETIC — no official SHB chart of legal or
collateral fields has been supplied (docs/OPEN_QUESTIONS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from creditops.application.ports.legal import EvidenceFact, LegalEvidenceView
from creditops.domain.legal import (
    CollateralDocumentStatus,
    ConfirmedFactCitation,
    EvidenceCitation,
    EvidenceGapItem,
    GapBlockingLevel,
    OwnershipInconsistencyItem,
)

#: ASSUMPTION (synthetic): canonical field-key prefix for the borrower's
#: registered legal name, used both as the controlled-check subject and as
#: one side of the ownership cross-check.
ENTITY_NAME_FIELD_KEY = "legal.entity.registered_name_vi"
#: ASSUMPTION (synthetic): the name recorded on the collateral title/ownership
#: document, cross-checked against the entity name above.
COLLATERAL_OWNER_FIELD_KEY = "collateral.asset.owner_name_vi"


def _status_field_key(doc_key: str) -> str:
    return f"collateral.documents.{doc_key}.status"


def _expiry_field_key(doc_key: str) -> str:
    return f"collateral.documents.{doc_key}.expiry_date"


@dataclass(frozen=True, slots=True)
class CollateralRequirement:
    """One required collateral-document type, grounded in a corpus clause."""

    doc_key: str
    label_vi: str
    corpus_clause_ref: str  # "<document_id>:<clause_id>" — for audit traceability
    requires_expiry_check: bool
    missing_blocking_level: GapBlockingLevel
    expired_blocking_level: GapBlockingLevel


#: The synthetic collateral document checklist (operationalizes
#: tai_san_bao_dam:TSBD-01..03 from the policy corpus).
COLLATERAL_CHECKLIST: tuple[CollateralRequirement, ...] = (
    CollateralRequirement(
        doc_key="giay_chung_nhan_qsdd",
        label_vi="Giấy chứng nhận quyền sử dụng đất/quyền sở hữu tài sản",
        corpus_clause_ref="tai_san_bao_dam:TSBD-01",
        requires_expiry_check=True,
        missing_blocking_level=GapBlockingLevel.BLOCKING,
        expired_blocking_level=GapBlockingLevel.BLOCKING,
    ),
    CollateralRequirement(
        doc_key="hop_dong_the_chap",
        label_vi="Hợp đồng thế chấp/cầm cố tài sản bảo đảm",
        corpus_clause_ref="tai_san_bao_dam:TSBD-02",
        requires_expiry_check=False,
        missing_blocking_level=GapBlockingLevel.BLOCKING,
        expired_blocking_level=GapBlockingLevel.CONDITIONAL,
    ),
    CollateralRequirement(
        doc_key="bien_ban_dinh_gia",
        label_vi="Biên bản định giá tài sản bảo đảm",
        corpus_clause_ref="tai_san_bao_dam:TSBD-03",
        requires_expiry_check=True,
        missing_blocking_level=GapBlockingLevel.CONDITIONAL,
        expired_blocking_level=GapBlockingLevel.CONDITIONAL,
    ),
)


@dataclass(frozen=True, slots=True)
class CollateralItemResult:
    """One evaluated checklist item, ready to become a domain CollateralDocumentItem."""

    document_type_key: str
    label_vi: str
    status: CollateralDocumentStatus
    citations: tuple[EvidenceCitation, ...]
    expiry_date: date | None
    notes_vi: str


@dataclass(frozen=True, slots=True)
class CollateralPreAnalysis:
    items: tuple[CollateralItemResult, ...]
    gaps: tuple[EvidenceGapItem, ...]


def _fact(view: LegalEvidenceView, field_key: str) -> EvidenceFact | None:
    return next(
        (item for item in view.confirmed_facts if item.field_key == field_key), None
    )


def _parse_date(raw: object) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def evaluate_collateral_checklist(
    view: LegalEvidenceView, *, as_of: date
) -> CollateralPreAnalysis:
    """Deterministically evaluate collateral-document completeness and expiry.

    Never guesses: a required document with no recorded status fact at all
    produces an Evidence Gap instead of a claimed PRESENT/MISSING item.
    """

    items: list[CollateralItemResult] = []
    gaps: list[EvidenceGapItem] = []

    for requirement in COLLATERAL_CHECKLIST:
        status_fact = _fact(view, _status_field_key(requirement.doc_key))
        if status_fact is None:
            gaps.append(
                EvidenceGapItem(
                    missing_information_vi=(
                        "Chưa có dữ kiện đã xác nhận về tình trạng tài liệu "
                        f"'{requirement.label_vi}'."
                    ),
                    why_needed_vi=(
                        "Cần để đánh giá tính đầy đủ hồ sơ tài sản bảo đảm theo "
                        f"danh mục kiểm tra ({requirement.corpus_clause_ref})."
                    ),
                    blocking_level=requirement.missing_blocking_level,
                    suggested_evidence_vi=(
                        f"{requirement.label_vi} do cán bộ phụ trách xác nhận.",
                    ),
                )
            )
            continue

        status_citation = ConfirmedFactCitation(
            confirmed_fact_id=status_fact.confirmed_fact_id
        )
        raw_status = str(status_fact.value)

        if raw_status == "MISSING":
            items.append(
                CollateralItemResult(
                    document_type_key=requirement.doc_key,
                    label_vi=requirement.label_vi,
                    status=CollateralDocumentStatus.MISSING,
                    citations=(status_citation,),
                    expiry_date=None,
                    notes_vi="",
                )
            )
            gaps.append(
                EvidenceGapItem(
                    missing_information_vi=(
                        f"Thiếu tài liệu '{requirement.label_vi}' trong hồ sơ "
                        "tài sản bảo đảm."
                    ),
                    why_needed_vi=(
                        "Bắt buộc theo danh mục kiểm tra tài sản bảo đảm "
                        f"({requirement.corpus_clause_ref})."
                    ),
                    blocking_level=requirement.missing_blocking_level,
                    suggested_evidence_vi=(
                        f"{requirement.label_vi} do cán bộ phụ trách xác nhận.",
                    ),
                )
            )
            continue

        if raw_status != "PRESENT":
            gaps.append(
                EvidenceGapItem(
                    missing_information_vi=(
                        "Giá trị tình trạng không hợp lệ cho tài liệu "
                        f"'{requirement.label_vi}': '{raw_status}'."
                    ),
                    why_needed_vi="Cần dữ kiện tình trạng hợp lệ (PRESENT/MISSING).",
                    blocking_level=GapBlockingLevel.CLARIFICATION,
                )
            )
            continue

        citations: list[EvidenceCitation] = [status_citation]
        expiry_date: date | None = None
        notes_vi = ""

        if requirement.requires_expiry_check:
            expiry_fact = _fact(view, _expiry_field_key(requirement.doc_key))
            if expiry_fact is None:
                gaps.append(
                    EvidenceGapItem(
                        missing_information_vi=(
                            "Chưa có ngày hết hạn được xác nhận cho tài liệu "
                            f"'{requirement.label_vi}'."
                        ),
                        why_needed_vi="Cần để xác định tài liệu còn hiệu lực hay đã hết hạn.",
                        blocking_level=GapBlockingLevel.CLARIFICATION,
                    )
                )
                notes_vi = "Chưa xác định được ngày hết hạn."
            else:
                parsed = _parse_date(expiry_fact.value)
                if parsed is None:
                    gaps.append(
                        EvidenceGapItem(
                            missing_information_vi=(
                                "Ngày hết hạn không hợp lệ cho tài liệu "
                                f"'{requirement.label_vi}'."
                            ),
                            why_needed_vi="Cần một ngày hợp lệ theo định dạng ISO.",
                            blocking_level=GapBlockingLevel.CLARIFICATION,
                        )
                    )
                else:
                    expiry_date = parsed
                    citations.append(
                        ConfirmedFactCitation(
                            confirmed_fact_id=expiry_fact.confirmed_fact_id
                        )
                    )
                    if parsed < as_of:
                        items.append(
                            CollateralItemResult(
                                document_type_key=requirement.doc_key,
                                label_vi=requirement.label_vi,
                                status=CollateralDocumentStatus.EXPIRED,
                                citations=tuple(citations),
                                expiry_date=parsed,
                                notes_vi=f"Hết hạn ngày {parsed.isoformat()}.",
                            )
                        )
                        gaps.append(
                            EvidenceGapItem(
                                missing_information_vi=(
                                    f"Tài liệu '{requirement.label_vi}' đã hết hạn "
                                    f"({parsed.isoformat()})."
                                ),
                                why_needed_vi=(
                                    "Cần bản cập nhật còn hiệu lực theo danh mục "
                                    f"kiểm tra ({requirement.corpus_clause_ref})."
                                ),
                                blocking_level=requirement.expired_blocking_level,
                                suggested_evidence_vi=(
                                    f"{requirement.label_vi} còn hiệu lực do cán bộ "
                                    "phụ trách xác nhận.",
                                ),
                            )
                        )
                        continue

        items.append(
            CollateralItemResult(
                document_type_key=requirement.doc_key,
                label_vi=requirement.label_vi,
                status=CollateralDocumentStatus.PRESENT,
                citations=tuple(citations),
                expiry_date=expiry_date,
                notes_vi=notes_vi,
            )
        )

    return CollateralPreAnalysis(items=tuple(items), gaps=tuple(gaps))


def check_ownership_consistency(
    view: LegalEvidenceView,
) -> tuple[OwnershipInconsistencyItem, ...]:
    """Deterministically flag a mismatch between the registered entity name
    and the name recorded on the collateral ownership document.

    A pure string comparison — it never asserts fraud or wrongdoing, only
    that two Confirmed Facts disagree; legal significance is for a human.
    """

    entity_fact = _fact(view, ENTITY_NAME_FIELD_KEY)
    collateral_fact = _fact(view, COLLATERAL_OWNER_FIELD_KEY)
    if entity_fact is None or collateral_fact is None:
        return ()
    entity_name = str(entity_fact.value).strip().casefold()
    collateral_owner = str(collateral_fact.value).strip().casefold()
    if not entity_name or not collateral_owner or entity_name == collateral_owner:
        return ()
    return (
        OwnershipInconsistencyItem(
            description_vi=(
                "Tên chủ thể đăng ký doanh nghiệp "
                f"('{entity_fact.value}') không khớp với tên chủ sở hữu ghi nhận "
                f"trên tài liệu tài sản bảo đảm ('{collateral_fact.value}')."
            ),
            citations=(
                ConfirmedFactCitation(confirmed_fact_id=entity_fact.confirmed_fact_id),
                ConfirmedFactCitation(
                    confirmed_fact_id=collateral_fact.confirmed_fact_id
                ),
            ),
        ),
    )


__all__ = [
    "COLLATERAL_CHECKLIST",
    "COLLATERAL_OWNER_FIELD_KEY",
    "ENTITY_NAME_FIELD_KEY",
    "CollateralItemResult",
    "CollateralPreAnalysis",
    "CollateralRequirement",
    "check_ownership_consistency",
    "evaluate_collateral_checklist",
]
