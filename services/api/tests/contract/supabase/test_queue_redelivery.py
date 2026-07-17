from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from creditops.application.ports.queue import QueueError
from creditops.domain.tasks import TaskEnvelopeV1
from creditops.infrastructure.supabase.queue import SupabaseQueue

NOW = datetime(2026, 7, 18, 5, 0, tzinfo=UTC)
TASK = UUID("30000000-0000-0000-0000-000000000001")
CASE = UUID("10000000-0000-0000-0000-000000000001")
DOC = UUID("20000000-0000-0000-0000-000000000001")


class Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class Connection:
    def __init__(self, rows: list[tuple[object, ...] | None]) -> None:
        self.rows = rows
        self.queries: list[str] = []
        self.params: list[tuple[object, ...] | None] = []

    async def execute(self, query: str, params: tuple[object, ...] | None = None) -> Cursor:
        self.queries.append(query)
        self.params.append(params)
        return Cursor(self.rows.pop(0) if self.rows else (True,))


def envelope() -> TaskEnvelopeV1:
    return TaskEnvelopeV1(
        task_id=TASK, case_id=CASE, case_version=1, document_version_id=DOC
    )


@pytest.mark.asyncio
async def test_queue_reads_without_pop_and_archives_only_explicitly() -> None:
    connection = Connection(
        [
            (42, 1, NOW, envelope().model_dump(mode="json"), NOW),
            (True,),
        ]
    )
    queue = SupabaseQueue(connection)
    message = await queue.read_one(visibility_timeout_seconds=300)
    assert message is not None
    assert message.message_id == 42
    assert message.envelope.task_id == TASK
    assert "pgmq.read" in connection.queries[0]
    assert "pgmq.pop" not in " ".join(connection.queries).lower()
    await queue.archive(42)
    assert "pgmq.archive" in connection.queries[1]


@pytest.mark.asyncio
async def test_queue_rejects_malformed_message_and_bounds_visibility() -> None:
    connection = Connection([(42, 1, NOW, {"task_id": "not-a-uuid"}, NOW)])
    queue = SupabaseQueue(connection)
    with pytest.raises(QueueError):
        await queue.read_one(visibility_timeout_seconds=300)
    with pytest.raises(QueueError):
        await queue.read_one(visibility_timeout_seconds=86_401)
