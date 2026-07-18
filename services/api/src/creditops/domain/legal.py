"""Structured output contract for the Legal, Compliance and Collateral Agent.

Design invariants (docs/AGENT_ARCHITECTURE.md, AGENTS.md, ADR-0002):

- The schema has NO field capable of expressing a final legal determination,
  a wrongdoing/violation declaration, a policy waiver, or an LLM-only
  collateral value.  ``extra="forbid"`` plus the module-level schema guard
  makes such a field a construction-time error, not a reviewable mistake.
  Only potential-issue phrasing is representable (``exceptions``,
  ``possible_issues``-style wording inside free text).
- Every material finding carries at least one evidence citation: a Confirmed
  Fact, a document region, a grounded policy citation, or a controlled-check
  reference.  A finding with no citations is structurally impossible.
- Policy findings must cite at least one ``PolicyCitation``.  A citation is
  grounded against the ``policy_hits`` recorded on the assessment itself
  (the exact clauses the retrieval step offered for this execution) — mirrors
  how ``UnderwritingAssessment`` grounds ``CalculatorResultCitation`` against
  its own ``calculator_results``.  A citation naming a document/clause/version
  outside that recorded set is rejected at construction time.
- Controlled-check interpretations must reference an ``invocation_id`` that
  is present in the ``controlled_check_results`` recorded on the assessment.
  The LLM cannot invoke tools or fabricate a result; it can only interpret a
  result that was actually produced and passed into its context.
- Exceptions are always framed as potential issues FOR HUMAN REVIEW, never as
  a legal conclusion; each carries citations and an explicit uncertainty
  statement.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from creditops.domain.ids import CaseId, ConfirmedFactId, DocumentVersionId, TaskId
from creditops.domain.underwriting import FORBIDDEN_DECISION_FIELD_NAMES
from creditops.domain.underwriting import ConfidenceLevel as ConfidenceLevel
from creditops.domain.underwriting import GapBlockingLevel as GapBlockingLevel

type LegalComplianceAssessmentId = UUID

LEGAL_AGENT_ROLE: Literal["LEGAL_COMPLIANCE_COLLATERAL"] = "LEGAL_COMPLIANCE_COLLATERAL"

#: Normalized field names that would express a legal/credit determination.
#: Extends the maker's forbidden-decision list with legal-conclusion and
#: collateral-valuation vocabulary; potential-issue phrasing only is allowed.
FORBIDDEN_LEGAL_FIELD_NAMES = FORBIDDEN_DECISION_FIELD_NAMES | frozenset(
    {
        "legalconclusion",
        "legaldetermination",
        "wrongdoing",
        "guilt",
        "guilty",
        "violationconfirmed",
        "violation",
        "collateralvalue",
        "appraisalvalue",
        "propertyvalue",
        "valuationamount",
        "kycresult",
        "amlresult",
        "compliancedetermination",
        "policywaiver",
    }
)


class ControlledCheckType(StrEnum):
    """The finite set of controlled checks the agent may only interpret."""

    KYC = "KYC"
    AML_WATCHLIST = "AML_WATCHLIST"
    RELATED_PARTY = "RELATED_PARTY"


class ControlledCheckStatus(StrEnum):
    CLEAR = "CLEAR"
    HIT = "HIT"
    INCONCLUSIVE = "INCONCLUSIVE"


class CollateralDocumentStatus(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    EXPIRED = "EXPIRED"


class ExceptionCategory(StrEnum):
    POLICY = "POLICY"
    LEGAL = "LEGAL"
    COLLATERAL = "COLLATERAL"


class ConfirmedFactCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["CONFIRMED_FACT"] = "CONFIRMED_FACT"
    confirmed_fact_id: ConfirmedFactId


class DocumentRegionCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["DOCUMENT_REGION"] = "DOCUMENT_REGION"
    document_version_id: DocumentVersionId
    region: str = Field(min_length=1, max_length=500)


class PolicyCitation(BaseModel):
    """A clause-level citation into the synthetic versioned policy corpus.

    Grounded at construction time against ``LegalComplianceAssessment.policy_hits``
    — the exact corpus id, version, document, clause and quoted text that the
    deterministic retrieval step actually offered for this execution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["POLICY_CITATION"] = "POLICY_CITATION"
    corpus_id: str = Field(min_length=1, max_length=200)
    corpus_version: str = Field(min_length=1, max_length=50)
    document_id: str = Field(min_length=1, max_length=200)
    clause_id: str = Field(min_length=1, max_length=50)
    quoted_text_vi: str = Field(min_length=1, max_length=2000)


class ControlledCheckCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["CONTROLLED_CHECK"] = "CONTROLLED_CHECK"
    invocation_id: UUID


EvidenceCitation = Annotated[
    ConfirmedFactCitation
    | DocumentRegionCitation
    | PolicyCitation
    | ControlledCheckCitation,
    Field(discriminator="kind"),
]


class Finding(BaseModel):
    """One material analytical statement, always evidence-cited."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement_vi: str = Field(min_length=1, max_length=4000)
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1)
    confidence: ConfidenceLevel
    uncertainty_vi: str = Field(default="", max_length=2000)


class AssessmentSection(BaseModel):
    """A narrative section built exclusively from cited findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Finding, ...] = Field(min_length=1)


class PolicyFinding(BaseModel):
    """A potentially-applicable-policy finding; requires >=1 PolicyCitation.

    ``possible_issue_vi`` is deliberately named to keep the statement framed
    as a potential issue for human review, never a policy conclusion.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    possible_issue_vi: str = Field(min_length=1, max_length=4000)
    citations: tuple[PolicyCitation, ...] = Field(min_length=1)
    confidence: ConfidenceLevel
    uncertainty_vi: str = Field(default="", max_length=2000)


class ControlledCheckInterpretation(BaseModel):
    """Interpretation of one controlled-check result the agent was given.

    ``invocation_id`` must reference a result carried in
    ``LegalComplianceAssessment.controlled_check_results`` — the LLM can
    neither invoke a tool nor fabricate one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    invocation_id: UUID
    statement_vi: str = Field(min_length=1, max_length=2000)
    confidence: ConfidenceLevel
    uncertainty_vi: str = Field(default="", max_length=2000)


class OwnershipInconsistencyItem(BaseModel):
    """A deterministically detected cross-fact ownership mismatch.

    Produced by a pure function over Confirmed Facts (never the LLM); at
    least two conflicting citations are required so the discrepancy is
    reproducible from the recorded evidence alone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    description_vi: str = Field(min_length=1, max_length=2000)
    citations: tuple[EvidenceCitation, ...] = Field(min_length=2)
    detected_by: Literal["DETERMINISTIC_CROSS_CHECK"] = "DETERMINISTIC_CROSS_CHECK"
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH


class OwnershipConsistencySection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Finding, ...] = Field(min_length=1)
    inconsistencies: tuple[OwnershipInconsistencyItem, ...] = ()


class CollateralDocumentItem(BaseModel):
    """One collateral-document checklist result: present, missing or expired."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_type_key: str = Field(min_length=1, max_length=200)
    label_vi: str = Field(min_length=1, max_length=300)
    status: CollateralDocumentStatus
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1)
    expiry_date: date | None = None
    notes_vi: str = Field(default="", max_length=1000)


class CollateralReviewSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_items: tuple[CollateralDocumentItem, ...] = ()
    ownership_evidence_findings: tuple[Finding, ...] = Field(min_length=1)


class ExceptionItem(BaseModel):
    """A potential policy/legal/collateral exception FOR HUMAN REVIEW ONLY.

    Never a legal conclusion or a disposition; ``uncertainty_vi`` is required
    (not defaulted) so an exception can never be stated without an explicit
    statement of what remains uncertain about it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: ExceptionCategory
    possible_issue_vi: str = Field(min_length=1, max_length=4000)
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1)
    confidence: ConfidenceLevel
    uncertainty_vi: str = Field(min_length=1, max_length=2000)


class AssumptionItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    statement_vi: str = Field(min_length=1, max_length=4000)
    rationale_vi: str = Field(min_length=1, max_length=4000)
    basis_citations: tuple[EvidenceCitation, ...] = ()


class EvidenceGapItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    missing_information_vi: str = Field(min_length=1, max_length=2000)
    why_needed_vi: str = Field(min_length=1, max_length=2000)
    blocking_level: GapBlockingLevel
    suggested_evidence_vi: tuple[str, ...] = ()


class PolicyHitRecord(BaseModel):
    """One clause the deterministic retrieval step offered for this execution.

    Recorded on the assessment as the ground truth ``PolicyCitation``
    grounding is checked against; produced only by ``PolicyCorpus`` retrieval,
    never by the LLM.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_id: str = Field(min_length=1, max_length=200)
    corpus_version: str = Field(min_length=1, max_length=50)
    document_id: str = Field(min_length=1, max_length=200)
    clause_id: str = Field(min_length=1, max_length=50)
    quoted_text_vi: str = Field(min_length=1, max_length=2000)


class ControlledCheckResultRecord(BaseModel):
    """One controlled-check result recorded on the assessment as ground truth.

    Mirrors the underwriting maker's ``calculator_results`` self-grounding
    technique: ``ControlledCheckInterpretation.invocation_id`` is checked
    against this tuple, never against a dynamically supplied external set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    invocation_id: UUID
    check_type: ControlledCheckType
    provider_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=200)
    tool_version: str = Field(min_length=1, max_length=50)
    subject_type: Literal["ENTITY", "INDIVIDUAL"]
    subject_ref_vi: str = Field(min_length=1, max_length=300)
    status: ControlledCheckStatus
    result_summary_vi: str = Field(min_length=1, max_length=1000)
    invoked_at: datetime
    is_mock: bool = True


class PolicyCorpusRef(BaseModel):
    """Which loaded, checksum-verified corpus this execution consulted.

    Recorded even when ``policy_hits`` ends up empty (no clause was cited),
    so the persistence layer can register the corpus version actually loaded
    without re-deriving a checksum from citation data.  ``None`` on the
    assessment means no corpus was configured for this execution (ADR-0002
    abstention path).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    checksum_sha256: str = Field(min_length=1, max_length=64)
    is_synthetic: bool = True


class LegalAssessmentProvenance(BaseModel):
    """Immutable provenance envelope recorded on every legal agent output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: CaseId
    case_version: int = Field(ge=1)
    agent_role: Literal["LEGAL_COMPLIANCE_COLLATERAL"] = LEGAL_AGENT_ROLE
    execution_id: UUID
    task_id: TaskId
    prompt_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)
    evidence_view_built_at: datetime
    created_at: datetime


class LegalComplianceAssessment(BaseModel):
    """The Legal/Compliance/Collateral agent's complete assessment.

    Append-only once persisted.  Contains potential-issue analysis, grounded
    policy findings, controlled-check interpretations, collateral-document
    completeness, exceptions for human review, assumptions and evidence gaps
    — and no legal determination, wrongdoing declaration, policy waiver, or
    LLM-derived collateral value of any kind.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: LegalComplianceAssessmentId
    provenance: LegalAssessmentProvenance
    legal_entity_review: AssessmentSection
    authority_signatory_review: AssessmentSection
    ownership_consistency: OwnershipConsistencySection
    policy_review: tuple[PolicyFinding, ...] = ()
    controlled_check_interpretations: tuple[ControlledCheckInterpretation, ...] = ()
    collateral_review: CollateralReviewSection
    exceptions: tuple[ExceptionItem, ...] = ()
    assumptions: tuple[AssumptionItem, ...] = ()
    evidence_gaps: tuple[EvidenceGapItem, ...] = ()
    policy_hits: tuple[PolicyHitRecord, ...] = ()
    policy_corpus_ref: PolicyCorpusRef | None = None
    controlled_check_results: tuple[ControlledCheckResultRecord, ...] = ()

    def _iter_findings(self) -> tuple[Finding, ...]:
        located: list[Finding] = []
        located.extend(self.legal_entity_review.findings)
        located.extend(self.authority_signatory_review.findings)
        located.extend(self.ownership_consistency.findings)
        located.extend(self.collateral_review.ownership_evidence_findings)
        return tuple(located)

    def _iter_all_citations(self) -> tuple[EvidenceCitation, ...]:
        citations: list[EvidenceCitation] = []
        for finding in self._iter_findings():
            citations.extend(finding.citations)
        for policy_finding in self.policy_review:
            citations.extend(policy_finding.citations)
        for item in self.collateral_review.document_items:
            citations.extend(item.citations)
        for inconsistency in self.ownership_consistency.inconsistencies:
            citations.extend(inconsistency.citations)
        for exception in self.exceptions:
            citations.extend(exception.citations)
        for assumption in self.assumptions:
            citations.extend(assumption.basis_citations)
        return tuple(citations)

    @model_validator(mode="after")
    def _policy_citations_are_grounded(self) -> Self:
        known_hits = {
            (hit.corpus_id, hit.corpus_version, hit.document_id, hit.clause_id, hit.quoted_text_vi)
            for hit in self.policy_hits
        }
        for citation in self._iter_all_citations():
            if citation.kind != "POLICY_CITATION":
                continue
            key = (
                citation.corpus_id,
                citation.corpus_version,
                citation.document_id,
                citation.clause_id,
                citation.quoted_text_vi,
            )
            if key not in known_hits:
                raise ValueError(
                    "policy citation does not resolve to a clause offered by "
                    f"retrieval: {citation.document_id}/{citation.clause_id} "
                    f"({citation.corpus_id} {citation.corpus_version})"
                )
        return self

    @model_validator(mode="after")
    def _controlled_check_references_are_grounded(self) -> Self:
        known_invocations = {
            result.invocation_id for result in self.controlled_check_results
        }
        for citation in self._iter_all_citations():
            if citation.kind != "CONTROLLED_CHECK":
                continue
            if citation.invocation_id not in known_invocations:
                raise ValueError(
                    "controlled-check citation references an unknown "
                    f"invocation id: {citation.invocation_id}"
                )
        for interpretation in self.controlled_check_interpretations:
            if interpretation.invocation_id not in known_invocations:
                raise ValueError(
                    "controlled-check interpretation references an unknown "
                    f"invocation id: {interpretation.invocation_id}"
                )
        return self

    @model_validator(mode="after")
    def _ownership_inconsistency_citations_are_distinct(self) -> Self:
        for inconsistency in self.ownership_consistency.inconsistencies:
            fact_ids = {
                citation.confirmed_fact_id
                for citation in inconsistency.citations
                if citation.kind == "CONFIRMED_FACT"
            }
            if len(fact_ids) < 2 and len(inconsistency.citations) < 2:
                raise ValueError(
                    "an ownership inconsistency must cite at least two "
                    "conflicting pieces of evidence"
                )
        return self


def _assert_no_forbidden_fields(model: type[BaseModel], seen: set[str]) -> None:
    name = model.__name__
    if name in seen:
        return
    seen.add(name)
    for field_name, field_info in model.model_fields.items():
        normalized = "".join(char for char in field_name.casefold() if char.isalnum())
        if normalized in FORBIDDEN_LEGAL_FIELD_NAMES:
            raise AssertionError(
                f"{name}.{field_name} would express a legal/credit determination"
            )
        annotation = field_info.annotation
        stack = [annotation]
        while stack:
            candidate = stack.pop()
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                _assert_no_forbidden_fields(candidate, seen)
            else:
                stack.extend(getattr(candidate, "__args__", ()))


# Import-time structural guard: the legal assessment schema can never grow a
# decision-capable or legal-determination field without failing every test
# run and worker start.
_assert_no_forbidden_fields(LegalComplianceAssessment, set())
