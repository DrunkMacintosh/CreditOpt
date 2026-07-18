"""Durable state + controlled-tool contracts for the Legal, Compliance and
Collateral Agent.

The repository exposes exactly what the reviewer use case needs: a scoped
evidence view (Confirmed Facts and the document inventory for the case
version — Candidate Facts are never authoritative input), an idempotent
append-only persist of the assessment plus its PROVISIONAL evidence gaps, the
reviewer->checker Handoff, and the controlled-check records, plus agent audit
events.  It exposes no way to satisfy a gate, resolve a gap or conflict,
confirm a fact, or record any legal/credit decision.

``ControlledChecksGateway`` is the ONLY way KYC, AML/watchlist and
related-party results reach the agent.  The LLM never calls a tool directly;
the application layer invokes this gateway deterministically, before
inference, and passes the typed, provenance-carrying results into the
model's context.  The only production-permitted implementations of this
Protocol are clearly-labelled mock/synthetic adapters (see
``infrastructure/mock/legal_checks.py``) — this project never wires a real
compliance provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from creditops.application.ports.orchestration import OrchestrationAuditEvent
from creditops.domain.legal import (
    ControlledCheckStatus,
    ControlledCheckType,
    GapBlockingLevel,
    LegalComplianceAssessment,
)

# --------------------------------------------------------------------------
# Scoped evidence view
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceFact:
    """One Confirmed Fact projected into the reviewer's scoped evidence view."""

    confirmed_fact_id: UUID
    field_key: str
    value: str | int | float | bool
    document_version_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentInventoryItem:
    """One document known for the case version, for citation and review."""

    document_version_id: UUID
    original_filename: str
    stage: str


@dataclass(frozen=True, slots=True)
class LegalEvidenceView:
    """Scoped, versioned view of the Credit Case Digital Twin for the reviewer."""

    case_id: UUID
    case_version: int
    built_at: datetime
    confirmed_facts: tuple[EvidenceFact, ...] = ()
    documents: tuple[DocumentInventoryItem, ...] = ()


# --------------------------------------------------------------------------
# Controlled-check wire contracts (KYC / AML+watchlist / related-party)
# --------------------------------------------------------------------------


class ControlledCheckError(RuntimeError):
    """Base class for failures invoking or validating a controlled check."""


class ControlledCheckUnavailableError(ControlledCheckError):
    """The configured controlled-check provider could not be reached."""


class ControlledCheckSubject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_type: Literal["ENTITY", "INDIVIDUAL"]
    subject_ref_vi: str = Field(min_length=1, max_length=300)


class ControlledCheckRequest(BaseModel):
    """A request to run exactly one controlled check for one subject.

    Carries provider id and correlation id for provenance; the application
    layer builds this deterministically from Confirmed Facts, never from LLM
    output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: str = Field(min_length=1, max_length=128)
    case_id: UUID
    check_type: ControlledCheckType
    subject: ControlledCheckSubject
    provider_id: str = Field(min_length=1, max_length=100)


class ControlledCheckResult(BaseModel):
    """A validated controlled-check result with a full provenance envelope.

    ``is_mock`` is always ``True`` for every adapter shipped in this project;
    the field exists so a future production adapter cannot silently claim
    mock provenance for a real compliance decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    invocation_id: UUID
    check_type: ControlledCheckType
    provider_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=200)
    tool_version: str = Field(min_length=1, max_length=50)
    subject: ControlledCheckSubject
    case_id: UUID
    status: ControlledCheckStatus
    result_summary_vi: str = Field(min_length=1, max_length=1000)
    result_payload: Mapping[str, Any] = Field(default_factory=dict)
    invoked_at: datetime
    is_mock: bool = True


class ControlledChecksGateway(Protocol):
    """Provider-neutral contract for the three controlled checks in scope."""

    async def check_kyc(
        self, request: ControlledCheckRequest
    ) -> ControlledCheckResult: ...

    async def check_aml_watchlist(
        self, request: ControlledCheckRequest
    ) -> ControlledCheckResult: ...

    async def check_related_party(
        self, request: ControlledCheckRequest
    ) -> ControlledCheckResult: ...


# --------------------------------------------------------------------------
# Durable state contracts
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProvisionalGapRecord:
    """A PROVISIONAL evidence gap the reviewer surfaces for human consideration."""

    issue_vi: str
    missing_information_vi: str
    blocking_level: GapBlockingLevel
    suggested_evidence_vi: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PersistedLegalOutput:
    """Durable identifiers of one persisted reviewer execution."""

    assessment_id: UUID
    handoff_id: UUID
    gap_ids: tuple[UUID, ...]
    controlled_check_record_ids: tuple[UUID, ...]
    handoff_state: str
    created: bool


@dataclass(frozen=True, slots=True)
class LatestLegalAssessmentRecord:
    """Read model for the latest persisted assessment plus its handoff status."""

    assessment_id: UUID
    case_id: UUID
    case_version: int
    execution_id: UUID
    agent_role: str
    prompt_version: str
    created_at: datetime
    assessment: Mapping[str, object]
    handoff_id: UUID | None
    handoff_state: str | None
    handoff_created_at: datetime | None


class LegalRepository(Protocol):
    async def load_evidence_view(self, case_id: UUID) -> LegalEvidenceView | None: ...

    async def load_latest_assessment(
        self, case_id: UUID
    ) -> LatestLegalAssessmentRecord | None: ...

    async def find_persisted(
        self,
        *,
        case_id: UUID,
        case_version: int,
        task_id: UUID,
    ) -> PersistedLegalOutput | None: ...

    async def persist_assessment(
        self,
        *,
        assessment: LegalComplianceAssessment,
        handoff_id: UUID,
        handoff_state: str,
        gaps: tuple[ProvisionalGapRecord, ...],
        controlled_checks: tuple[ControlledCheckResult, ...],
    ) -> PersistedLegalOutput: ...

    async def append_audit(self, event: OrchestrationAuditEvent) -> None: ...
