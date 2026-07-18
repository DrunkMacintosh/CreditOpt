"""Legal reviewer: evidence view -> pre-analysis -> bounded inference.

Order is non-negotiable, mirroring ``application/underwriting/maker.py``: the
deterministic collateral checklist, expiry detection, ownership cross-check,
policy retrieval and controlled checks ALL run FIRST.  The LLM then receives
their results and may only reference them by id through a closed JSON
response schema — policy citations are validated against ``const``-pinned
branches built from the actual retrieved clauses, and controlled-check
interpretations against an enum of the invocation ids that were actually
produced.  A well-formed response cannot cite a clause outside the retrieved
set or a check that was never run.  With no configured reasoning endpoint
there is NO assessment (fail closed).  With no configured policy corpus the
``policy_review`` schema is forced to an empty array — the model is
structurally unable to state any policy conclusion, per ADR-0002.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from creditops.application.legal.controlled_checks import ControlledCheckSuite
from creditops.application.legal.corpus import PolicyCorpus, PolicyHit
from creditops.application.legal.evidence import CollateralPreAnalysis
from creditops.application.ports.legal import (
    ControlledCheckResult,
    ControlledCheckSubject,
    LegalEvidenceView,
    LegalRepository,
    ProvisionalGapRecord,
)
from creditops.application.ports.model_gateway import (
    InferenceGateway,
    ReasonRequest,
)
from creditops.domain.legal import (
    AssessmentSection,
    AssumptionItem,
    CollateralDocumentItem,
    CollateralReviewSection,
    ConfidenceLevel,
    ConfirmedFactCitation,
    ControlledCheckCitation,
    ControlledCheckInterpretation,
    ControlledCheckResultRecord,
    DocumentRegionCitation,
    EvidenceCitation,
    EvidenceGapItem,
    ExceptionCategory,
    ExceptionItem,
    Finding,
    GapBlockingLevel,
    LegalAssessmentProvenance,
    LegalComplianceAssessment,
    OwnershipConsistencySection,
    OwnershipInconsistencyItem,
    PolicyCitation,
    PolicyCorpusRef,
    PolicyFinding,
    PolicyHitRecord,
)

LEGAL_PROMPT_VERSION = "legal-prompt-v1"
LEGAL_SCHEMA_VERSION = "legal-assessment-v1"
RISK_REVIEW_HANDOFF_STATE = "READY_FOR_RISK_REVIEW"


class ReviewerOutputInvalid(ValueError):
    """The LLM response failed deterministic validation; bounded retry applies."""


class LegalPrompt:
    """Load the versioned Vietnamese trusted-instruction reviewer prompt."""

    version = LEGAL_PROMPT_VERSION

    def __init__(self, text: str | None = None) -> None:
        self._text = text if text is not None else self._load()

    @staticmethod
    def _load() -> str:
        return (
            resources.files("creditops.prompts.legal")
            .joinpath("v1.md")
            .read_text(encoding="utf-8")
        )

    @property
    def text(self) -> str:
        return self._text


def _policy_citation_branches(hits: Sequence[PolicyHit]) -> list[Mapping[str, Any]]:
    return [
        {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind",
                "corpus_id",
                "corpus_version",
                "document_id",
                "clause_id",
                "quoted_text_vi",
            ],
            "properties": {
                "kind": {"const": "POLICY_CITATION"},
                "corpus_id": {"const": hit.corpus_id},
                "corpus_version": {"const": hit.corpus_version},
                "document_id": {"const": hit.document_id},
                "clause_id": {"const": hit.clause_id},
                "quoted_text_vi": {"const": hit.quoted_text_vi},
            },
        }
        for hit in hits
    ]


def _controlled_check_citation_branches(
    invocation_ids: Sequence[str],
) -> list[Mapping[str, Any]]:
    return [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "invocation_id"],
            "properties": {
                "kind": {"const": "CONTROLLED_CHECK"},
                "invocation_id": {"const": invocation_id},
            },
        }
        for invocation_id in invocation_ids
    ]


def _citation_schema(
    fact_ids: Sequence[str],
    document_version_ids: Sequence[str],
    hits: Sequence[PolicyHit],
    invocation_ids: Sequence[str],
) -> Mapping[str, Any]:
    branches: list[Mapping[str, Any]] = []
    if fact_ids:
        branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "confirmed_fact_id"],
                "properties": {
                    "kind": {"const": "CONFIRMED_FACT"},
                    "confirmed_fact_id": {"type": "string", "enum": list(fact_ids)},
                },
            }
        )
    if document_version_ids:
        branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "document_version_id", "region"],
                "properties": {
                    "kind": {"const": "DOCUMENT_REGION"},
                    "document_version_id": {
                        "type": "string",
                        "enum": list(document_version_ids),
                    },
                    "region": {"type": "string", "minLength": 1, "maxLength": 500},
                },
            }
        )
    branches.extend(_policy_citation_branches(hits))
    branches.extend(_controlled_check_citation_branches(invocation_ids))
    return {"oneOf": branches}


def _finding_schema(citation: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["statement_vi", "citations", "confidence"],
        "properties": {
            "statement_vi": {"type": "string", "minLength": 1, "maxLength": 4000},
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": citation,
            },
            "confidence": {"enum": ["HIGH", "MEDIUM", "LOW"]},
            "uncertainty_vi": {"type": "string", "maxLength": 2000},
        },
    }


def _section_schema(finding: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings"],
        "properties": {
            "findings": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": finding,
            }
        },
    }


def build_response_schema(
    *,
    fact_ids: Sequence[str],
    document_version_ids: Sequence[str],
    policy_hits: Sequence[PolicyHit],
    invocation_ids: Sequence[str],
) -> Mapping[str, Any]:
    """Closed response schema.  Policy citations are pinned (``const``) to the
    exact retrieved clauses; controlled-check citations are pinned to the
    exact invocation ids actually produced.  A well-formed response cannot
    invent a clause, a check result, or a legal/credit decision field."""

    citation = _citation_schema(fact_ids, document_version_ids, policy_hits, invocation_ids)
    finding = _finding_schema(citation)
    section = _section_schema(finding)

    policy_citation_only = {"oneOf": _policy_citation_branches(policy_hits)}
    policy_finding = {
        "type": "object",
        "additionalProperties": False,
        "required": ["possible_issue_vi", "citations", "confidence"],
        "properties": {
            "possible_issue_vi": {"type": "string", "minLength": 1, "maxLength": 4000},
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": policy_citation_only,
            },
            "confidence": {"enum": ["HIGH", "MEDIUM", "LOW"]},
            "uncertainty_vi": {"type": "string", "maxLength": 2000},
        },
    }
    policy_review_schema: Mapping[str, Any] = (
        {"type": "array", "maxItems": 20, "items": policy_finding}
        if policy_hits
        # Fail closed per ADR-0002: no corpus configured -> the model cannot
        # emit a single policy_review entry, positive or negative.
        else {"type": "array", "maxItems": 0}
    )

    interpretation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["invocation_id", "statement_vi", "confidence"],
        "properties": {
            "invocation_id": {"type": "string", "enum": list(invocation_ids)},
            "statement_vi": {"type": "string", "minLength": 1, "maxLength": 2000},
            "confidence": {"enum": ["HIGH", "MEDIUM", "LOW"]},
            "uncertainty_vi": {"type": "string", "maxLength": 2000},
        },
    }
    interpretations_schema: Mapping[str, Any] = (
        {"type": "array", "maxItems": 10, "items": interpretation}
        if invocation_ids
        else {"type": "array", "maxItems": 0}
    )

    exception_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "category",
            "possible_issue_vi",
            "citations",
            "confidence",
            "uncertainty_vi",
        ],
        "properties": {
            "category": {"enum": ["POLICY", "LEGAL", "COLLATERAL"]},
            "possible_issue_vi": {"type": "string", "minLength": 1, "maxLength": 4000},
            "citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": citation,
            },
            "confidence": {"enum": ["HIGH", "MEDIUM", "LOW"]},
            "uncertainty_vi": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "legal_entity_review",
            "authority_signatory_review",
            "ownership_consistency",
            "policy_review",
            "controlled_check_interpretations",
            "collateral_review",
            "exceptions",
            "assumptions",
            "evidence_gaps",
        ],
        "properties": {
            "legal_entity_review": section,
            "authority_signatory_review": section,
            "ownership_consistency": section,
            "policy_review": policy_review_schema,
            "controlled_check_interpretations": interpretations_schema,
            "collateral_review": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ownership_evidence_findings"],
                "properties": {"ownership_evidence_findings": section["properties"]["findings"]},
            },
            "exceptions": {"type": "array", "maxItems": 20, "items": exception_item},
            "assumptions": {
                "type": "array",
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["statement_vi", "rationale_vi"],
                    "properties": {
                        "statement_vi": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 4000,
                        },
                        "rationale_vi": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 4000,
                        },
                        "basis_citations": {
                            "type": "array",
                            "maxItems": 20,
                            "items": citation,
                        },
                    },
                },
            },
            "evidence_gaps": {
                "type": "array",
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "missing_information_vi",
                        "why_needed_vi",
                        "blocking_level",
                    ],
                    "properties": {
                        "missing_information_vi": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 2000,
                        },
                        "why_needed_vi": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 2000,
                        },
                        "blocking_level": {
                            "enum": ["BLOCKING", "CONDITIONAL", "CLARIFICATION"]
                        },
                        "suggested_evidence_vi": {
                            "type": "array",
                            "maxItems": 10,
                            "items": {"type": "string", "maxLength": 500},
                        },
                    },
                },
            },
        },
    }


def build_untrusted_context(
    view: LegalEvidenceView,
    *,
    policy_hits: Sequence[PolicyHit],
    controlled_checks: ControlledCheckSuite,
    collateral_pre_analysis: CollateralPreAnalysis,
    ownership_inconsistencies: Sequence[OwnershipInconsistencyItem],
    corpus_disclaimer_vi: str | None,
) -> str:
    """Serialize the scoped evidence for the prompt's untrusted-data region."""

    payload: dict[str, Any] = {
        "caseId": str(view.case_id),
        "caseVersion": view.case_version,
        "confirmedFacts": [
            {
                "confirmedFactId": str(fact.confirmed_fact_id),
                "fieldKey": fact.field_key,
                "value": fact.value,
            }
            for fact in view.confirmed_facts
        ],
        "documents": [
            {
                "documentVersionId": str(item.document_version_id),
                "originalFilename": item.original_filename,
                "stage": item.stage,
            }
            for item in view.documents
        ],
        "policyCorpus": {
            "configured": bool(policy_hits) or corpus_disclaimer_vi is not None,
            "disclaimerVi": corpus_disclaimer_vi,
            "hits": [
                {
                    "corpusId": hit.corpus_id,
                    "corpusVersion": hit.corpus_version,
                    "documentId": hit.document_id,
                    "documentTitleVi": hit.document_title_vi,
                    "clauseId": hit.clause_id,
                    "quotedTextVi": hit.quoted_text_vi,
                }
                for hit in policy_hits
            ],
        },
        "controlledCheckResults": [
            {
                "invocationId": str(result.invocation_id),
                "checkType": result.check_type.value,
                "status": result.status.value,
                "resultSummaryVi": result.result_summary_vi,
                "toolName": result.tool_name,
                "toolVersion": result.tool_version,
                "isMock": result.is_mock,
            }
            for result in controlled_checks.results
        ],
        "collateralPreAnalysis": {
            "items": [
                {
                    "documentTypeKey": item.document_type_key,
                    "labelVi": item.label_vi,
                    "status": item.status.value,
                    "expiryDate": item.expiry_date.isoformat()
                    if item.expiry_date
                    else None,
                    "notesVi": item.notes_vi,
                }
                for item in collateral_pre_analysis.items
            ],
        },
        "ownershipInconsistencies": [
            {"descriptionVi": item.description_vi} for item in ownership_inconsistencies
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _citations_from(
    raw: Sequence[Mapping[str, Any]],
    *,
    view: LegalEvidenceView,
    policy_hits: Sequence[PolicyHit],
    invocation_ids: Sequence[str],
) -> tuple[EvidenceCitation, ...]:
    known_fact_ids = {str(fact.confirmed_fact_id) for fact in view.confirmed_facts}
    known_document_ids = {str(item.document_version_id) for item in view.documents}
    known_hits = {
        (hit.corpus_id, hit.corpus_version, hit.document_id, hit.clause_id, hit.quoted_text_vi)
        for hit in policy_hits
    }
    known_invocations = set(invocation_ids)
    citations: list[EvidenceCitation] = []
    for item in raw:
        kind = item.get("kind")
        if kind == "CONFIRMED_FACT":
            fact_id = str(item.get("confirmed_fact_id", ""))
            if fact_id not in known_fact_ids:
                raise ReviewerOutputInvalid(
                    f"citation references a confirmed fact outside the scoped "
                    f"evidence view: {fact_id}"
                )
            citations.append(ConfirmedFactCitation(confirmed_fact_id=UUID(fact_id)))
        elif kind == "DOCUMENT_REGION":
            document_id = str(item.get("document_version_id", ""))
            if document_id not in known_document_ids:
                raise ReviewerOutputInvalid(
                    f"citation references a document outside the scoped "
                    f"evidence view: {document_id}"
                )
            citations.append(
                DocumentRegionCitation(
                    document_version_id=UUID(document_id),
                    region=str(item.get("region", "")),
                )
            )
        elif kind == "POLICY_CITATION":
            key = (
                str(item.get("corpus_id", "")),
                str(item.get("corpus_version", "")),
                str(item.get("document_id", "")),
                str(item.get("clause_id", "")),
                str(item.get("quoted_text_vi", "")),
            )
            if key not in known_hits:
                raise ReviewerOutputInvalid(
                    "policy citation does not resolve to a clause retrieval "
                    f"offered for this execution: {key}"
                )
            citations.append(
                PolicyCitation(
                    corpus_id=key[0],
                    corpus_version=key[1],
                    document_id=key[2],
                    clause_id=key[3],
                    quoted_text_vi=key[4],
                )
            )
        elif kind == "CONTROLLED_CHECK":
            invocation_id = str(item.get("invocation_id", ""))
            if invocation_id not in known_invocations:
                raise ReviewerOutputInvalid(
                    f"citation references an unknown controlled-check "
                    f"invocation id: {invocation_id}"
                )
            citations.append(
                ControlledCheckCitation(invocation_id=UUID(invocation_id))
            )
        else:
            raise ReviewerOutputInvalid(f"unsupported citation kind: {kind!r}")
    return tuple(citations)


def _finding_from(
    item: Mapping[str, Any],
    *,
    view: LegalEvidenceView,
    policy_hits: Sequence[PolicyHit],
    invocation_ids: Sequence[str],
) -> Finding:
    raw_citations = item.get("citations")
    if not isinstance(raw_citations, list) or not raw_citations:
        raise ReviewerOutputInvalid("a finding without citations is not acceptable")
    return Finding(
        statement_vi=str(item.get("statement_vi", "")),
        citations=_citations_from(
            raw_citations, view=view, policy_hits=policy_hits, invocation_ids=invocation_ids
        ),
        confidence=ConfidenceLevel(str(item.get("confidence", ""))),
        uncertainty_vi=str(item.get("uncertainty_vi", "")),
    )


def _findings_from(
    payload: Mapping[str, Any],
    key: str,
    *,
    view: LegalEvidenceView,
    policy_hits: Sequence[PolicyHit],
    invocation_ids: Sequence[str],
) -> tuple[Finding, ...]:
    section = payload.get(key)
    if not isinstance(section, Mapping):
        raise ReviewerOutputInvalid(f"section {key} is missing")
    raw = section.get("findings")
    if not isinstance(raw, list):
        raise ReviewerOutputInvalid(f"section {key} has no findings list")
    return tuple(
        _finding_from(item, view=view, policy_hits=policy_hits, invocation_ids=invocation_ids)
        for item in raw
        if isinstance(item, Mapping)
    )


@dataclass(frozen=True, slots=True)
class ReviewerRunContext:
    """Identity of one reviewer execution, recorded in provenance."""

    task_id: UUID
    execution_id: UUID
    correlation_id: str


class BuildAssessment:
    """Deterministically validate an LLM payload into a LegalComplianceAssessment.

    Any structural or grounding problem raises ``ReviewerOutputInvalid`` — the
    caller converts that into the bounded durable retry path; nothing invalid
    is ever persisted.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4

    def build(
        self,
        *,
        payload: Mapping[str, Any],
        view: LegalEvidenceView,
        policy_hits: Sequence[PolicyHit],
        controlled_checks: ControlledCheckSuite,
        collateral_pre_analysis: CollateralPreAnalysis,
        ownership_inconsistencies: Sequence[OwnershipInconsistencyItem],
        corpus: PolicyCorpus | None,
        run: ReviewerRunContext,
        model_id: str,
        endpoint_id: str,
    ) -> LegalComplianceAssessment:
        try:
            return self._build(
                payload=payload,
                view=view,
                policy_hits=policy_hits,
                controlled_checks=controlled_checks,
                collateral_pre_analysis=collateral_pre_analysis,
                ownership_inconsistencies=ownership_inconsistencies,
                corpus=corpus,
                run=run,
                model_id=model_id,
                endpoint_id=endpoint_id,
            )
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            if isinstance(exc, ReviewerOutputInvalid):
                raise
            raise ReviewerOutputInvalid(f"reviewer output rejected: {exc}") from exc

    def _build(
        self,
        *,
        payload: Mapping[str, Any],
        view: LegalEvidenceView,
        policy_hits: Sequence[PolicyHit],
        controlled_checks: ControlledCheckSuite,
        collateral_pre_analysis: CollateralPreAnalysis,
        ownership_inconsistencies: Sequence[OwnershipInconsistencyItem],
        corpus: PolicyCorpus | None,
        run: ReviewerRunContext,
        model_id: str,
        endpoint_id: str,
    ) -> LegalComplianceAssessment:
        invocation_ids = controlled_checks.invocation_ids()

        def findings(key: str) -> tuple[Finding, ...]:
            return _findings_from(
                payload, key, view=view, policy_hits=policy_hits, invocation_ids=invocation_ids
            )

        ownership_raw = payload.get("ownership_consistency")
        if not isinstance(ownership_raw, Mapping):
            raise ReviewerOutputInvalid("section ownership_consistency is missing")

        policy_raw = payload.get("policy_review", [])
        if not isinstance(policy_raw, list):
            raise ReviewerOutputInvalid("policy_review must be a list")
        if not policy_hits and policy_raw:
            raise ReviewerOutputInvalid(
                "policy findings present without a configured policy corpus"
            )
        policy_review = tuple(
            PolicyFinding(
                possible_issue_vi=str(item.get("possible_issue_vi", "")),
                citations=tuple(
                    citation
                    for citation in _citations_from(
                        list(item.get("citations", [])),
                        view=view,
                        policy_hits=policy_hits,
                        invocation_ids=invocation_ids,
                    )
                    if isinstance(citation, PolicyCitation)
                ),
                confidence=ConfidenceLevel(str(item.get("confidence", ""))),
                uncertainty_vi=str(item.get("uncertainty_vi", "")),
            )
            for item in policy_raw
            if isinstance(item, Mapping)
        )

        interpretations_raw = payload.get("controlled_check_interpretations", [])
        if not isinstance(interpretations_raw, list):
            raise ReviewerOutputInvalid(
                "controlled_check_interpretations must be a list"
            )
        interpretations = tuple(
            ControlledCheckInterpretation(
                invocation_id=UUID(str(item.get("invocation_id", ""))),
                statement_vi=str(item.get("statement_vi", "")),
                confidence=ConfidenceLevel(str(item.get("confidence", ""))),
                uncertainty_vi=str(item.get("uncertainty_vi", "")),
            )
            for item in interpretations_raw
            if isinstance(item, Mapping)
        )
        for interpretation in interpretations:
            if str(interpretation.invocation_id) not in invocation_ids:
                raise ReviewerOutputInvalid(
                    "controlled-check interpretation references an unknown "
                    f"invocation id: {interpretation.invocation_id}"
                )

        collateral_raw = payload.get("collateral_review")
        if not isinstance(collateral_raw, Mapping):
            raise ReviewerOutputInvalid("section collateral_review is missing")
        ownership_evidence_raw = collateral_raw.get("ownership_evidence_findings")
        if not isinstance(ownership_evidence_raw, list) or not ownership_evidence_raw:
            raise ReviewerOutputInvalid(
                "collateral_review.ownership_evidence_findings is required"
            )
        ownership_evidence_findings = tuple(
            _finding_from(
                item, view=view, policy_hits=policy_hits, invocation_ids=invocation_ids
            )
            for item in ownership_evidence_raw
            if isinstance(item, Mapping)
        )
        document_items = tuple(
            CollateralDocumentItem(
                document_type_key=item.document_type_key,
                label_vi=item.label_vi,
                status=item.status,
                citations=item.citations,
                expiry_date=item.expiry_date,
                notes_vi=item.notes_vi,
            )
            for item in collateral_pre_analysis.items
        )

        exceptions_raw = payload.get("exceptions", [])
        if not isinstance(exceptions_raw, list):
            raise ReviewerOutputInvalid("exceptions must be a list")
        exceptions = tuple(
            ExceptionItem(
                category=ExceptionCategory(str(item.get("category", ""))),
                possible_issue_vi=str(item.get("possible_issue_vi", "")),
                citations=_citations_from(
                    list(item.get("citations", [])),
                    view=view,
                    policy_hits=policy_hits,
                    invocation_ids=invocation_ids,
                ),
                confidence=ConfidenceLevel(str(item.get("confidence", ""))),
                uncertainty_vi=str(item.get("uncertainty_vi", "")),
            )
            for item in exceptions_raw
            if isinstance(item, Mapping)
        )

        assumptions_raw = payload.get("assumptions", [])
        if not isinstance(assumptions_raw, list):
            raise ReviewerOutputInvalid("assumptions must be a list")
        assumptions = tuple(
            AssumptionItem(
                statement_vi=str(item.get("statement_vi", "")),
                rationale_vi=str(item.get("rationale_vi", "")),
                basis_citations=_citations_from(
                    list(item.get("basis_citations", [])),
                    view=view,
                    policy_hits=policy_hits,
                    invocation_ids=invocation_ids,
                ),
            )
            for item in assumptions_raw
            if isinstance(item, Mapping)
        )

        llm_gaps_raw = payload.get("evidence_gaps", [])
        if not isinstance(llm_gaps_raw, list):
            raise ReviewerOutputInvalid("evidence_gaps must be a list")
        llm_gaps = tuple(
            EvidenceGapItem(
                missing_information_vi=str(item.get("missing_information_vi", "")),
                why_needed_vi=str(item.get("why_needed_vi", "")),
                blocking_level=GapBlockingLevel(str(item.get("blocking_level", ""))),
                suggested_evidence_vi=tuple(
                    str(entry) for entry in item.get("suggested_evidence_vi", [])
                ),
            )
            for item in llm_gaps_raw
            if isinstance(item, Mapping)
        )

        deterministic_gaps = list(collateral_pre_analysis.gaps)
        for missing_check in controlled_checks.missing:
            deterministic_gaps.append(
                EvidenceGapItem(
                    missing_information_vi=(
                        f"Không thể thực hiện kiểm tra {missing_check.check_type.value}: "
                        f"{missing_check.reason}"
                    ),
                    why_needed_vi="Cần để diễn giải kết quả kiểm tra kiểm soát.",
                    blocking_level=missing_check.blocking_level,
                )
            )
        if not policy_hits:
            deterministic_gaps.append(
                EvidenceGapItem(
                    missing_information_vi=(
                        "Không có kho chính sách nào được cấu hình cho thẩm định pháp lý."
                    ),
                    why_needed_vi=(
                        "Cần một kho chính sách tổng hợp (synthetic) đã được cấu hình "
                        "phiên bản và kiểm tra checksum trước khi trả lời câu hỏi chính "
                        "sách (ADR-0002)."
                    ),
                    blocking_level=GapBlockingLevel.CONDITIONAL,
                )
            )
        seen = {gap.missing_information_vi for gap in deterministic_gaps}
        merged_gaps = tuple(deterministic_gaps) + tuple(
            gap for gap in llm_gaps if gap.missing_information_vi not in seen
        )

        now = self._clock()
        return LegalComplianceAssessment(
            id=self._id_factory(),
            provenance=LegalAssessmentProvenance(
                case_id=view.case_id,
                case_version=view.case_version,
                execution_id=run.execution_id,
                task_id=run.task_id,
                prompt_version=LEGAL_PROMPT_VERSION,
                model_id=model_id,
                endpoint_id=endpoint_id,
                evidence_view_built_at=view.built_at,
                created_at=now,
            ),
            legal_entity_review=AssessmentSection(findings=findings("legal_entity_review")),
            authority_signatory_review=AssessmentSection(
                findings=findings("authority_signatory_review")
            ),
            ownership_consistency=OwnershipConsistencySection(
                findings=findings("ownership_consistency"),
                inconsistencies=tuple(ownership_inconsistencies),
            ),
            policy_review=policy_review,
            controlled_check_interpretations=interpretations,
            collateral_review=CollateralReviewSection(
                document_items=document_items,
                ownership_evidence_findings=ownership_evidence_findings,
            ),
            exceptions=exceptions,
            assumptions=assumptions,
            evidence_gaps=merged_gaps,
            policy_hits=tuple(
                PolicyHitRecord(
                    corpus_id=hit.corpus_id,
                    corpus_version=hit.corpus_version,
                    document_id=hit.document_id,
                    clause_id=hit.clause_id,
                    quoted_text_vi=hit.quoted_text_vi,
                )
                for hit in policy_hits
            ),
            policy_corpus_ref=(
                PolicyCorpusRef(
                    corpus_id=corpus.corpus_id,
                    version=corpus.version,
                    checksum_sha256=corpus.checksum_sha256,
                    is_synthetic=corpus.is_synthetic,
                )
                if corpus is not None
                else None
            ),
            controlled_check_results=tuple(
                ControlledCheckResultRecord(
                    invocation_id=result.invocation_id,
                    check_type=result.check_type,
                    provider_id=result.provider_id,
                    tool_name=result.tool_name,
                    tool_version=result.tool_version,
                    subject_type=result.subject.subject_type,
                    subject_ref_vi=result.subject.subject_ref_vi,
                    status=result.status,
                    result_summary_vi=result.result_summary_vi,
                    invoked_at=result.invoked_at,
                    is_mock=result.is_mock,
                )
                for result in controlled_checks.results
            ),
        )


class RunLegalInference:
    """Call the reasoning endpoint with the closed reviewer schema and validate."""

    def __init__(
        self,
        gateway: InferenceGateway,
        *,
        prompt: LegalPrompt | None = None,
        builder: BuildAssessment | None = None,
    ) -> None:
        self._gateway = gateway
        self._prompt = prompt or LegalPrompt()
        self._builder = builder or BuildAssessment()

    @property
    def prompt_version(self) -> str:
        return self._prompt.version

    async def infer(
        self,
        *,
        view: LegalEvidenceView,
        policy_hits: Sequence[PolicyHit],
        controlled_checks: ControlledCheckSuite,
        collateral_pre_analysis: CollateralPreAnalysis,
        ownership_inconsistencies: Sequence[OwnershipInconsistencyItem],
        corpus: PolicyCorpus | None,
        run: ReviewerRunContext,
    ) -> LegalComplianceAssessment:
        fact_ids = tuple(str(fact.confirmed_fact_id) for fact in view.confirmed_facts)
        document_ids = tuple(str(item.document_version_id) for item in view.documents)
        schema = build_response_schema(
            fact_ids=fact_ids,
            document_version_ids=document_ids,
            policy_hits=policy_hits,
            invocation_ids=controlled_checks.invocation_ids(),
        )
        result = await self._gateway.reason(
            ReasonRequest(
                correlation_id=run.correlation_id,
                case_id=view.case_id,
                content=build_untrusted_context(
                    view,
                    policy_hits=policy_hits,
                    controlled_checks=controlled_checks,
                    collateral_pre_analysis=collateral_pre_analysis,
                    ownership_inconsistencies=ownership_inconsistencies,
                    corpus_disclaimer_vi=corpus.disclaimer_vi if corpus is not None else None,
                ),
                response_schema=schema,
                system_context=self._prompt.text,
            )
        )
        if not isinstance(result.payload, Mapping):
            raise ReviewerOutputInvalid("reviewer output is not a JSON object")
        return self._builder.build(
            payload=result.payload,
            view=view,
            policy_hits=policy_hits,
            controlled_checks=controlled_checks,
            collateral_pre_analysis=collateral_pre_analysis,
            ownership_inconsistencies=ownership_inconsistencies,
            corpus=corpus,
            run=run,
            model_id=result.model_id,
            endpoint_id=result.endpoint_id,
        )


def controlled_check_results_from_assessment(
    assessment: LegalComplianceAssessment,
) -> tuple[ControlledCheckResult, ...]:
    """Reconstruct port-level results from the assessment's own record.

    Used only on the crash-then-resume path (persistence resumed from the
    ``CHECKPOINT_INFERENCE`` checkpoint, where the live controlled-check
    suite is no longer in scope).  ``result_payload`` is not embedded in the
    domain record, so it round-trips as an empty mapping; every field that
    matters for grounding, provenance, and the durable record is preserved.
    """

    return tuple(
        ControlledCheckResult(
            invocation_id=record.invocation_id,
            check_type=record.check_type,
            provider_id=record.provider_id,
            tool_name=record.tool_name,
            tool_version=record.tool_version,
            subject=ControlledCheckSubject(
                subject_type=record.subject_type,
                subject_ref_vi=record.subject_ref_vi,
            ),
            case_id=assessment.provenance.case_id,
            status=record.status,
            result_summary_vi=record.result_summary_vi,
            result_payload={},
            invoked_at=record.invoked_at,
            is_mock=record.is_mock,
        )
        for record in assessment.controlled_check_results
    )


def gap_records_from(
    assessment: LegalComplianceAssessment,
) -> tuple[ProvisionalGapRecord, ...]:
    return tuple(
        ProvisionalGapRecord(
            issue_vi=gap.why_needed_vi,
            missing_information_vi=gap.missing_information_vi,
            blocking_level=gap.blocking_level,
            suggested_evidence_vi=gap.suggested_evidence_vi,
        )
        for gap in assessment.evidence_gaps
    )


async def persist_reviewer_output(
    repository: LegalRepository,
    assessment: LegalComplianceAssessment,
    controlled_checks: tuple[ControlledCheckResult, ...],
    *,
    handoff_id: UUID,
) -> Any:
    """Persist assessment + controlled-check records + PROVISIONAL gaps + handoff."""

    return await repository.persist_assessment(
        assessment=assessment,
        handoff_id=handoff_id,
        handoff_state=RISK_REVIEW_HANDOFF_STATE,
        gaps=gap_records_from(assessment),
        controlled_checks=controlled_checks,
    )


__all__ = [
    "LEGAL_PROMPT_VERSION",
    "LEGAL_SCHEMA_VERSION",
    "RISK_REVIEW_HANDOFF_STATE",
    "BuildAssessment",
    "LegalPrompt",
    "ReviewerOutputInvalid",
    "ReviewerRunContext",
    "RunLegalInference",
    "build_response_schema",
    "build_untrusted_context",
    "controlled_check_results_from_assessment",
    "gap_records_from",
    "persist_reviewer_output",
]
