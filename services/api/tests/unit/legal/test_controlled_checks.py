"""Controlled-check suite tests: provenance + invocation-id grounding (mock only).

All subject references are synthetic and created solely for demonstration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from creditops.application.legal.controlled_checks import (
    SUBJECT_FIELD_KEY,
    run_controlled_checks,
)
from creditops.application.ports.legal import (
    ControlledCheckError,
    ControlledCheckRequest,
    ControlledCheckResult,
    ControlledCheckSubject,
    ControlledCheckUnavailableError,
    EvidenceFact,
    LegalEvidenceView,
)
from creditops.domain.legal import (
    ControlledCheckInterpretation,
    ControlledCheckStatus,
    ControlledCheckType,
)
from creditops.infrastructure.mock.legal_checks import MockControlledChecksGateway

NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
CASE_ID = uuid4()


def make_view(subject_name: str | None) -> LegalEvidenceView:
    facts = (
        (
            EvidenceFact(
                confirmed_fact_id=uuid4(),
                field_key=SUBJECT_FIELD_KEY,
                value=subject_name,
                document_version_id=uuid4(),
            ),
        )
        if subject_name is not None
        else ()
    )
    return LegalEvidenceView(
        case_id=CASE_ID, case_version=1, built_at=NOW, confirmed_facts=facts
    )


class TestProvenance:
    @pytest.mark.asyncio
    async def test_every_result_carries_a_full_provenance_envelope(self) -> None:
        view = make_view("Cong ty TNHH Van Tai Thanh Cong Demo")
        gateway = MockControlledChecksGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t1")
        assert len(suite.results) == 3
        for result in suite.results:
            assert isinstance(result.invocation_id, UUID)
            assert result.provider_id
            assert result.tool_name
            assert result.tool_version
            assert result.invoked_at == NOW
            assert result.is_mock is True
            assert result.check_type in {
                ControlledCheckType.KYC,
                ControlledCheckType.AML_WATCHLIST,
                ControlledCheckType.RELATED_PARTY,
            }

    @pytest.mark.asyncio
    async def test_check_types_are_kyc_aml_and_related_party(self) -> None:
        view = make_view("Cong ty TNHH Van Tai Thanh Cong Demo")
        gateway = MockControlledChecksGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t1")
        assert {r.check_type for r in suite.results} == {
            ControlledCheckType.KYC,
            ControlledCheckType.AML_WATCHLIST,
            ControlledCheckType.RELATED_PARTY,
        }

    @pytest.mark.asyncio
    async def test_hit_marker_deterministically_produces_a_hit(self) -> None:
        view = make_view("Cong ty TNHH WATCHLIST-HIT-DEMO Nam Bac")
        gateway = MockControlledChecksGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t2")
        watchlist = next(
            r for r in suite.results if r.check_type == ControlledCheckType.AML_WATCHLIST
        )
        assert watchlist.status == ControlledCheckStatus.HIT

    @pytest.mark.asyncio
    async def test_missing_subject_fact_produces_gaps_for_every_check(self) -> None:
        view = make_view(None)
        gateway = MockControlledChecksGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t3")
        assert suite.results == ()
        assert len(suite.missing) == 3

    @pytest.mark.asyncio
    async def test_provider_failure_produces_a_gap_without_failing_others(self) -> None:
        class FlakyGateway(MockControlledChecksGateway):
            async def check_aml_watchlist(
                self, request: ControlledCheckRequest
            ) -> ControlledCheckResult:
                raise ControlledCheckUnavailableError("provider timeout")

        view = make_view("Cong ty TNHH Van Tai Thanh Cong Demo")
        gateway = FlakyGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t4")
        assert len(suite.results) == 2
        assert len(suite.missing) == 1
        assert suite.missing[0].check_type == ControlledCheckType.AML_WATCHLIST


class TestInvocationIdGrounding:
    @pytest.mark.asyncio
    async def test_interpretation_can_reference_a_real_invocation_id(self) -> None:
        view = make_view("Cong ty TNHH Van Tai Thanh Cong Demo")
        gateway = MockControlledChecksGateway(clock=lambda: NOW)
        suite = await run_controlled_checks(gateway, view, correlation_id="legal:t5")
        real_id = suite.results[0].invocation_id
        interpretation = ControlledCheckInterpretation(
            invocation_id=real_id,
            statement_vi="Khong phat hien canh bao.",
            confidence="HIGH",  # type: ignore[arg-type]
        )
        assert interpretation.invocation_id == real_id
        assert str(real_id) in suite.invocation_ids()

    def test_controlled_check_error_is_the_base_of_unavailable_error(self) -> None:
        assert issubclass(ControlledCheckUnavailableError, ControlledCheckError)

    def test_controlled_check_result_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ControlledCheckResult.model_validate(
                {
                    "invocation_id": str(uuid4()),
                    "check_type": "KYC",
                    "provider_id": "synthetic-mock-compliance-provider",
                    "tool_name": "synthetic-kyc-mock",
                    "tool_version": "mock-v1",
                    "subject": {
                        "subject_type": "ENTITY",
                        "subject_ref_vi": "Cong ty TNHH Demo",
                    },
                    "case_id": str(uuid4()),
                    "status": "CLEAR",
                    "result_summary_vi": "Khong phat hien.",
                    "invoked_at": NOW.isoformat(),
                    "is_mock": True,
                    "kyc_result_confirmed": True,
                }
            )

    def test_subject_ref_is_never_a_real_credential(self) -> None:
        subject = ControlledCheckSubject(
            subject_type="ENTITY", subject_ref_vi="Cong ty TNHH Demo"
        )
        assert "password" not in subject.subject_ref_vi.casefold()
