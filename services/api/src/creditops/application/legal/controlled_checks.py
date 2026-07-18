"""Scoped evidence view -> controlled-check suite for the reviewer.

Mirrors ``application/underwriting/evidence.py``'s calculator-suite pattern:
requests are built deterministically from Confirmed Facts (never from LLM
output) and every configured check is invoked BEFORE inference.  The LLM
never invokes a tool; it only interprets a ``ControlledCheckResult`` that was
actually produced and is passed into its context.  A check whose required
subject fact is absent, or whose provider is unavailable, becomes a recorded
Evidence Gap rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from creditops.application.ports.legal import (
    ControlledCheckError,
    ControlledCheckRequest,
    ControlledCheckResult,
    ControlledChecksGateway,
    ControlledCheckSubject,
    LegalEvidenceView,
)
from creditops.domain.legal import ControlledCheckType, GapBlockingLevel

#: ASSUMPTION (synthetic): the canonical field key carrying the subject the
#: three controlled checks run against.  No official SHB chart of legal
#: fields has been supplied (docs/OPEN_QUESTIONS.md).
SUBJECT_FIELD_KEY = "legal.entity.registered_name_vi"

#: Provider identifier recorded on every mock check request/result.
MOCK_PROVIDER_ID = "synthetic-mock-compliance-provider"


@dataclass(frozen=True, slots=True)
class MissingControlledCheck:
    """A controlled check that could not be run for this execution."""

    check_type: ControlledCheckType
    reason: str
    blocking_level: GapBlockingLevel


@dataclass(frozen=True, slots=True)
class ControlledCheckSuite:
    """Every controlled-check result produced for one scoped evidence view."""

    results: tuple[ControlledCheckResult, ...]
    missing: tuple[MissingControlledCheck, ...]

    def invocation_ids(self) -> tuple[str, ...]:
        return tuple(str(result.invocation_id) for result in self.results)


def _subject_from(view: LegalEvidenceView) -> ControlledCheckSubject | None:
    fact = next(
        (item for item in view.confirmed_facts if item.field_key == SUBJECT_FIELD_KEY),
        None,
    )
    if fact is None or isinstance(fact.value, bool):
        return None
    subject_ref = str(fact.value).strip()
    if not subject_ref:
        return None
    return ControlledCheckSubject(subject_type="ENTITY", subject_ref_vi=subject_ref)


async def run_controlled_checks(
    gateway: ControlledChecksGateway,
    view: LegalEvidenceView,
    *,
    correlation_id: str,
) -> ControlledCheckSuite:
    """Run KYC, AML/watchlist and related-party checks for the scoped subject.

    Every check is attempted independently: one provider failure produces a
    recorded gap for that check only, it never blocks the others or forces
    the whole task to fail closed (only a missing/unavailable reasoning
    gateway does that, per the existing failure policy).
    """

    subject = _subject_from(view)
    if subject is None:
        no_subject: tuple[MissingControlledCheck, ...] = tuple(
            MissingControlledCheck(
                check_type=check_type,
                reason=f"no confirmed fact for '{SUBJECT_FIELD_KEY}'",
                blocking_level=GapBlockingLevel.BLOCKING,
            )
            for check_type in ControlledCheckType
        )
        return ControlledCheckSuite(results=(), missing=no_subject)

    calls = {
        ControlledCheckType.KYC: gateway.check_kyc,
        ControlledCheckType.AML_WATCHLIST: gateway.check_aml_watchlist,
        ControlledCheckType.RELATED_PARTY: gateway.check_related_party,
    }
    results: list[ControlledCheckResult] = []
    missing: list[MissingControlledCheck] = []
    for check_type, call in calls.items():
        request = ControlledCheckRequest(
            correlation_id=f"{correlation_id}:{check_type.value}",
            case_id=view.case_id,
            check_type=check_type,
            subject=subject,
            provider_id=MOCK_PROVIDER_ID,
        )
        try:
            results.append(await call(request))
        except ControlledCheckError as exc:
            missing.append(
                MissingControlledCheck(
                    check_type=check_type,
                    reason=str(exc)[:500],
                    blocking_level=GapBlockingLevel.CONDITIONAL,
                )
            )
    return ControlledCheckSuite(results=tuple(results), missing=tuple(missing))


__all__ = [
    "MOCK_PROVIDER_ID",
    "SUBJECT_FIELD_KEY",
    "ControlledCheckSuite",
    "MissingControlledCheck",
    "run_controlled_checks",
]
