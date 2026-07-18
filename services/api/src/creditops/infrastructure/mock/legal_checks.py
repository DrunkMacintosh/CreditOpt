"""Mock KYC/AML-watchlist/related-party adapters — NOT a production compliance
check.

Deterministic, fixture-driven: the result for a given subject reference is a
pure function of the subject text and check type, so tests are reproducible
without a network call.  Every result is stamped ``is_mock=True`` and a
synthetic ``tool_name``/``tool_version`` so it can never be mistaken for a
real KYC/AML/related-party provider.  This is the ONLY controlled-check
adapter this project wires; AGENTS.md forbids running production compliance
checks from this agent.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from creditops.application.ports.legal import (
    ControlledCheckRequest,
    ControlledCheckResult,
)
from creditops.domain.legal import ControlledCheckStatus, ControlledCheckType

#: ASSUMPTION (synthetic): subject reference strings containing these markers
#: deterministically trigger a HIT for demonstration purposes only. No real
#: watchlist, sanctions list, or related-party register is consulted.
_HIT_MARKERS: dict[ControlledCheckType, str] = {
    ControlledCheckType.KYC: "KYC-HIT-DEMO",
    ControlledCheckType.AML_WATCHLIST: "WATCHLIST-HIT-DEMO",
    ControlledCheckType.RELATED_PARTY: "RELATED-PARTY-HIT-DEMO",
}

_TOOL_NAMES: dict[ControlledCheckType, str] = {
    ControlledCheckType.KYC: "synthetic-kyc-mock",
    ControlledCheckType.AML_WATCHLIST: "synthetic-aml-watchlist-mock",
    ControlledCheckType.RELATED_PARTY: "synthetic-related-party-mock",
}
_TOOL_VERSION = "mock-v1"


class MockControlledChecksGateway:
    """Fixture-driven mock — not a production compliance check."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[ControlledCheckRequest], UUID] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or _deterministic_invocation_id

    async def check_kyc(self, request: ControlledCheckRequest) -> ControlledCheckResult:
        return self._respond(request)

    async def check_aml_watchlist(
        self, request: ControlledCheckRequest
    ) -> ControlledCheckResult:
        return self._respond(request)

    async def check_related_party(
        self, request: ControlledCheckRequest
    ) -> ControlledCheckResult:
        return self._respond(request)

    def _respond(self, request: ControlledCheckRequest) -> ControlledCheckResult:
        marker = _HIT_MARKERS[request.check_type]
        is_hit = marker in request.subject.subject_ref_vi
        status = ControlledCheckStatus.HIT if is_hit else ControlledCheckStatus.CLEAR
        summary = (
            f"Phát hiện khớp trong dữ liệu mô phỏng cho '{marker}' "
            "(mock — không phải kiểm tra tuân thủ thực tế)."
            if is_hit
            else "Không phát hiện khớp trong dữ liệu mô phỏng "
            "(mock — không phải kiểm tra tuân thủ thực tế)."
        )
        return ControlledCheckResult(
            invocation_id=self._id_factory(request),
            check_type=request.check_type,
            provider_id=request.provider_id,
            tool_name=_TOOL_NAMES[request.check_type],
            tool_version=_TOOL_VERSION,
            subject=request.subject,
            case_id=request.case_id,
            status=status,
            result_summary_vi=summary,
            result_payload={
                "mock": True,
                "matchedMarker": marker if is_hit else None,
            },
            invoked_at=self._clock(),
            is_mock=True,
        )


def _deterministic_invocation_id(request: ControlledCheckRequest) -> UUID:
    return uuid5(
        NAMESPACE_OID,
        f"legal-controlled-check:{request.correlation_id}:{request.check_type.value}",
    )


__all__ = ["MockControlledChecksGateway"]
