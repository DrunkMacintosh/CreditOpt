"""Durable Postgres adapter for the Legal, Compliance and Collateral Agent.

Bounded writes only: an append-only assessment insert deduplicated per
(case, case version, task), append-only controlled-check records, PROVISIONAL
evidence-gap inserts, one immutable reviewer->checker handoff, a
policy-corpus-version registry upsert, and agent audit events.  Nothing here
can satisfy a gate, resolve a gap, confirm a fact, or record a legal/credit
decision.  The evidence view reads Confirmed Facts and the document inventory
exclusively — candidate facts are never authoritative input.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from creditops.application.legal.reviewer import RISK_REVIEW_HANDOFF_STATE
from creditops.application.ports.legal import (
    ControlledCheckResult,
    DocumentInventoryItem,
    EvidenceFact,
    LatestLegalAssessmentRecord,
    LegalEvidenceView,
    PersistedLegalOutput,
    ProvisionalGapRecord,
)
from creditops.application.ports.orchestration import OrchestrationAuditEvent
from creditops.domain.legal import LEGAL_AGENT_ROLE, LegalComplianceAssessment
from creditops.infrastructure.postgres.orchestration import ConnectionFactory
from creditops.infrastructure.postgres.repositories import DatabaseConnection

_ACTOR_TYPE = f"AGENT:{LEGAL_AGENT_ROLE}"


class PostgresLegalRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    async def load_evidence_view(self, case_id: UUID) -> LegalEvidenceView | None:
        async with self._connection_factory() as connection:
            cursor = await connection.execute(
                "select case_version from public.credit_cases where id = %s",
                (case_id,),
            )
            case_row = await cursor.fetchone()
            if case_row is None:
                return None
            case_version = int(case_row[0])

            cursor = await connection.execute(
                """
                select id, field_key, value, document_version_id
                from public.confirmed_facts
                where case_id = %s and case_version = %s and stale_at is null
                order by created_at
                """,
                (case_id, case_version),
            )
            facts = tuple(
                EvidenceFact(
                    confirmed_fact_id=cast(UUID, row[0]),
                    field_key=str(row[1]),
                    value=cast("str | int | float | bool", row[2]),
                    document_version_id=cast(UUID, row[3]),
                )
                for row in await cursor.fetchall()
            )

            cursor = await connection.execute(
                """
                select id, original_filename, stage
                from public.document_versions
                where case_id = %s and case_version = %s and stale_at is null
                order by created_at
                """,
                (case_id, case_version),
            )
            documents = tuple(
                DocumentInventoryItem(
                    document_version_id=cast(UUID, row[0]),
                    original_filename=str(row[1]),
                    stage=str(row[2]),
                )
                for row in await cursor.fetchall()
            )
        return LegalEvidenceView(
            case_id=case_id,
            case_version=case_version,
            built_at=datetime.now(UTC),
            confirmed_facts=facts,
            documents=documents,
        )

    async def load_latest_assessment(
        self, case_id: UUID
    ) -> LatestLegalAssessmentRecord | None:
        async with self._connection_factory() as connection:
            cursor = await connection.execute(
                """
                select a.id, a.case_id, a.case_version, a.execution_id,
                       a.agent_role, a.prompt_version, a.created_at,
                       a.assessment, a.task_id
                from public.legal_compliance_assessments as a
                where a.case_id = %s
                order by a.created_at desc
                limit 1
                """,
                (case_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            task_id = cast(UUID, row[8])
            case_version = int(row[2])
            cursor = await connection.execute(
                """
                select id, state, created_at from public.handoffs
                where case_id = %s and case_version = %s
                  and source_task_id = %s and state = %s and stale_at is null
                order by created_at desc
                limit 1
                """,
                (case_id, case_version, task_id, RISK_REVIEW_HANDOFF_STATE),
            )
            handoff_row = await cursor.fetchone()
        return LatestLegalAssessmentRecord(
            assessment_id=cast(UUID, row[0]),
            case_id=cast(UUID, row[1]),
            case_version=case_version,
            execution_id=cast(UUID, row[3]),
            agent_role=str(row[4]),
            prompt_version=str(row[5]),
            created_at=cast(datetime, row[6]),
            assessment=cast("dict[str, object]", row[7]),
            handoff_id=cast(UUID, handoff_row[0]) if handoff_row else None,
            handoff_state=str(handoff_row[1]) if handoff_row else None,
            handoff_created_at=(
                cast(datetime, handoff_row[2]) if handoff_row else None
            ),
        )

    async def find_persisted(
        self,
        *,
        case_id: UUID,
        case_version: int,
        task_id: UUID,
    ) -> PersistedLegalOutput | None:
        async with self._connection_factory() as connection:
            cursor = await connection.execute(
                """
                select id from public.legal_compliance_assessments
                where case_id = %s and case_version = %s and task_id = %s
                """,
                (case_id, case_version, task_id),
            )
            assessment_row = await cursor.fetchone()
            if assessment_row is None:
                return None
            assessment_id = cast(UUID, assessment_row[0])
            handoff_id, handoff_state = await self._find_handoff(
                connection, case_id, case_version, task_id
            )
            gap_ids = await self._find_gap_ids(connection, case_id, case_version, task_id)
            check_ids = await self._find_controlled_check_ids(
                connection, case_id, case_version, task_id
            )
        if handoff_id is None:
            return None
        return PersistedLegalOutput(
            assessment_id=assessment_id,
            handoff_id=handoff_id,
            gap_ids=gap_ids,
            controlled_check_record_ids=check_ids,
            handoff_state=handoff_state,
            created=False,
        )

    async def persist_assessment(
        self,
        *,
        assessment: LegalComplianceAssessment,
        handoff_id: UUID,
        handoff_state: str,
        gaps: tuple[ProvisionalGapRecord, ...],
        controlled_checks: tuple[ControlledCheckResult, ...],
    ) -> PersistedLegalOutput:
        provenance = assessment.provenance
        async with self._connection_factory() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    insert into public.legal_compliance_assessments (
                      id, case_id, case_version, task_id, execution_id,
                      agent_role, prompt_version, model_id, endpoint_id,
                      assessment, assessment_schema_version,
                      evidence_view_built_at
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      'legal-assessment-v1', %s
                    )
                    on conflict (case_id, case_version, task_id) do nothing
                    returning id
                    """,
                    (
                        assessment.id,
                        provenance.case_id,
                        provenance.case_version,
                        provenance.task_id,
                        provenance.execution_id,
                        provenance.agent_role,
                        provenance.prompt_version,
                        provenance.model_id,
                        provenance.endpoint_id,
                        Jsonb(assessment.model_dump(mode="json")),
                        provenance.evidence_view_built_at,
                    ),
                )
                inserted = await cursor.fetchone()
                if inserted is None:
                    # A prior delivery persisted this reviewer output; the
                    # store is append-only, so return the existing identifiers.
                    cursor = await connection.execute(
                        """
                        select id from public.legal_compliance_assessments
                        where case_id = %s and case_version = %s and task_id = %s
                        """,
                        (
                            provenance.case_id,
                            provenance.case_version,
                            provenance.task_id,
                        ),
                    )
                    existing = await cursor.fetchone()
                    if existing is None:
                        raise RuntimeError("assessment idempotency row disappeared")
                    existing_handoff, existing_state = await self._find_handoff(
                        connection,
                        provenance.case_id,
                        provenance.case_version,
                        provenance.task_id,
                    )
                    if existing_handoff is None:
                        raise RuntimeError("persisted assessment has no handoff")
                    return PersistedLegalOutput(
                        assessment_id=cast(UUID, existing[0]),
                        handoff_id=existing_handoff,
                        gap_ids=await self._find_gap_ids(
                            connection,
                            provenance.case_id,
                            provenance.case_version,
                            provenance.task_id,
                        ),
                        controlled_check_record_ids=await self._find_controlled_check_ids(
                            connection,
                            provenance.case_id,
                            provenance.case_version,
                            provenance.task_id,
                        ),
                        handoff_state=existing_state,
                        created=False,
                    )

                corpus_ref = assessment.policy_corpus_ref
                if corpus_ref is not None:
                    await connection.execute(
                        """
                        insert into public.policy_corpus_versions (
                          corpus_id, version, checksum_sha256, loaded_at,
                          active, is_synthetic
                        ) values (%s, %s, %s, clock_timestamp(), true, %s)
                        on conflict (corpus_id, version) do update
                          set loaded_at = excluded.loaded_at, active = true
                        """,
                        (
                            corpus_ref.corpus_id,
                            corpus_ref.version,
                            corpus_ref.checksum_sha256,
                            corpus_ref.is_synthetic,
                        ),
                    )

                check_ids: list[UUID] = []
                for result in controlled_checks:
                    check_ids.append(result.invocation_id)
                    await connection.execute(
                        """
                        insert into public.controlled_check_records (
                          id, case_id, case_version, task_id, check_type,
                          provider_id, tool_name, tool_version, subject_type,
                          subject_ref_vi, status, result_summary_vi,
                          result_payload, is_mock, invoked_at
                        ) values (
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s
                        )
                        on conflict (id) do nothing
                        """,
                        (
                            result.invocation_id,
                            provenance.case_id,
                            provenance.case_version,
                            provenance.task_id,
                            result.check_type.value,
                            result.provider_id,
                            result.tool_name,
                            result.tool_version,
                            result.subject.subject_type,
                            result.subject.subject_ref_vi,
                            result.status.value,
                            result.result_summary_vi,
                            Jsonb(dict(result.result_payload)),
                            result.is_mock,
                            result.invoked_at,
                        ),
                    )

                gap_ids: list[UUID] = []
                for gap in gaps:
                    gap_id = uuid4()
                    await connection.execute(
                        """
                        insert into public.evidence_gaps (
                          id, case_id, case_version, affected_task_id, status,
                          blocking_level, issue_vi, missing_information_vi,
                          suggested_evidence_vi, created_by_type
                        ) values (
                          %s, %s, %s, %s, 'PROVISIONAL', %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            gap_id,
                            provenance.case_id,
                            provenance.case_version,
                            provenance.task_id,
                            gap.blocking_level.value,
                            gap.issue_vi,
                            gap.missing_information_vi,
                            Jsonb(list(gap.suggested_evidence_vi)),
                            _ACTOR_TYPE,
                        ),
                    )
                    gap_ids.append(gap_id)

                await connection.execute(
                    """
                    insert into public.handoffs (
                      id, case_id, case_version, source_task_id, state,
                      handoff_data, created_by_type
                    ) values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        handoff_id,
                        provenance.case_id,
                        provenance.case_version,
                        provenance.task_id,
                        handoff_state,
                        Jsonb(
                            {
                                "assessmentId": str(assessment.id),
                                "executionId": str(provenance.execution_id),
                                "schemaVersion": "legal-assessment-v1",
                            }
                        ),
                        _ACTOR_TYPE,
                    ),
                )
        return PersistedLegalOutput(
            assessment_id=assessment.id,
            handoff_id=handoff_id,
            gap_ids=tuple(gap_ids),
            controlled_check_record_ids=tuple(check_ids),
            handoff_state=handoff_state,
            created=True,
        )

    async def append_audit(self, event: OrchestrationAuditEvent) -> None:
        event_data = dict(event.event_data)
        event_data["executionId"] = str(event.execution_id)
        async with self._connection_factory() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into public.audit_events (
                      case_id, case_version, event_type, actor_type, actor_id,
                      artifact_type, artifact_id, event_data
                    ) values (%s, %s, %s, %s, null, %s, %s, %s)
                    """,
                    (
                        event.case_id,
                        event.case_version,
                        event.event_type,
                        _ACTOR_TYPE,
                        event.artifact_type,
                        event.artifact_id,
                        Jsonb(event_data),
                    ),
                )

    @staticmethod
    async def _find_handoff(
        connection: DatabaseConnection,
        case_id: UUID,
        case_version: int,
        task_id: UUID,
    ) -> tuple[UUID | None, str]:
        cursor = await connection.execute(
            """
            select id, state from public.handoffs
            where case_id = %s and case_version = %s and source_task_id = %s
              and state = %s and stale_at is null
            order by created_at desc
            limit 1
            """,
            (case_id, case_version, task_id, RISK_REVIEW_HANDOFF_STATE),
        )
        row = await cursor.fetchone()
        if row is None:
            return None, RISK_REVIEW_HANDOFF_STATE
        return cast(UUID, row[0]), str(row[1])

    @staticmethod
    async def _find_gap_ids(
        connection: DatabaseConnection,
        case_id: UUID,
        case_version: int,
        task_id: UUID,
    ) -> tuple[UUID, ...]:
        cursor = await connection.execute(
            """
            select id from public.evidence_gaps
            where case_id = %s and case_version = %s
              and affected_task_id = %s and created_by_type = %s
            order by created_at
            """,
            (case_id, case_version, task_id, _ACTOR_TYPE),
        )
        rows = await cursor.fetchall()
        return tuple(cast(UUID, row[0]) for row in rows)

    @staticmethod
    async def _find_controlled_check_ids(
        connection: DatabaseConnection,
        case_id: UUID,
        case_version: int,
        task_id: UUID,
    ) -> tuple[UUID, ...]:
        cursor = await connection.execute(
            """
            select id from public.controlled_check_records
            where case_id = %s and case_version = %s and task_id = %s
            order by created_at
            """,
            (case_id, case_version, task_id),
        )
        rows = await cursor.fetchall()
        return tuple(cast(UUID, row[0]) for row in rows)
