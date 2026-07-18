"""Task-lease renewal during a long-running stage (P0-A worker safety).

The worker must renew ``processing_tasks.lease_until`` on a bounded interval
while a stage is in flight; otherwise a long provider call outlives its lease
and ``reclaim_stranded`` reclaims the task, duplicating side effects.  These
failure-injection tests drive :class:`RunWorkerOnce` with a background heartbeat
and assert the abandon-on-lost-lease and structured-cancellation contracts.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from creditops.application.ports.queue import (
    QueueMessage,
    RetryDecision,
    TaskCheckpoint,
    TaskLeaseLost,
    TaskRecord,
)
from creditops.application.use_cases.run_worker_once import (
    RunWorkerOnce,
    StageResult,
    WorkerOutcome,
)
from creditops.domain.enums import TaskStatus
from creditops.domain.tasks import TaskEnvelopeV1

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
CASE = UUID("10000000-0000-0000-0000-000000000001")
DOC = UUID("20000000-0000-0000-0000-000000000001")
TASK = UUID("30000000-0000-0000-0000-000000000001")


def _envelope() -> TaskEnvelopeV1:
    return TaskEnvelopeV1(
        task_id=TASK, case_id=CASE, case_version=1, document_version_id=DOC
    )


def _task() -> TaskRecord:
    return TaskRecord(
        id=TASK,
        case_id=CASE,
        case_version=1,
        document_version_id=DOC,
        status=TaskStatus.PENDING,
        attempt_count=0,
        max_attempts=3,
        available_at=NOW,
        lease_token=None,
        lease_until=None,
        input_schema_version="1",
        input_payload={"storageBucket": "creditops-originals"},
        idempotency_key="UPLOAD:lease",
    )


class OneShotQueue:
    def __init__(self) -> None:
        self.message = QueueMessage(7, 1, NOW, NOW, _envelope())
        self.read = False
        self.archived: list[int] = []
        self.visibility_extensions = 0

    async def send(self, envelope: object, *, delay_seconds: int = 0) -> int:
        del envelope, delay_seconds
        return 8

    async def read_one(self, *, visibility_timeout_seconds: int) -> QueueMessage | None:
        del visibility_timeout_seconds
        if self.read:
            return None
        self.read = True
        return self.message

    async def extend_visibility(
        self, message_id: int, *, visibility_timeout_seconds: int
    ) -> None:
        del message_id, visibility_timeout_seconds
        self.visibility_extensions += 1

    async def archive(self, message_id: int) -> None:
        self.archived.append(message_id)


class LeaseTasks:
    """Task double whose ``extend_task_lease`` is scripted per test.

    ``lease_mode`` selects the failure injection:

    * ``"ok"`` -- always renews (a working heartbeat).
    * ``"false_after_first"`` -- renews the initial heartbeat, then returns
      ``False`` (lease silently reclaimed).
    * ``"raise_after_first"`` -- renews once, then raises ``TaskLeaseLost``.
    """

    def __init__(self, lease_mode: str = "ok") -> None:
        self.record = _task()
        self.lease_mode = lease_mode
        self.slot = False
        self.extend_calls = 0
        self.checkpoint_calls = 0
        self.succeeded = False
        self.superseded_calls = 0
        self.retry_calls = 0

    async def acquire_worker_slot(self, **kwargs: object) -> bool:
        del kwargs
        if self.slot:
            return False
        self.slot = True
        return True

    async def release_worker_slot(self, **kwargs: object) -> None:
        del kwargs
        self.slot = False

    async def extend_task_lease(self, **kwargs: object) -> bool:
        del kwargs
        self.extend_calls += 1
        if self.extend_calls == 1:
            return True
        if self.lease_mode == "false_after_first":
            return False
        if self.lease_mode == "raise_after_first":
            raise TaskLeaseLost("task lease reclaimed mid-inference")
        return True

    async def reclaim_stranded(self, **kwargs: object) -> tuple[UUID, ...]:
        del kwargs
        return ()

    async def claim(self, **kwargs: object) -> TaskRecord | None:
        token = kwargs["lease_token"]
        assert isinstance(token, UUID)
        if self.record.status not in (TaskStatus.PENDING, TaskStatus.RETRY_WAIT):
            return None
        self.record = replace(
            self.record, status=TaskStatus.RUNNING, lease_token=token
        )
        return self.record

    async def get(
        self,
        task_id: UUID,
        *,
        case_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> TaskRecord | None:
        del case_id, actor_id
        return self.record if task_id == self.record.id else None

    async def latest_checkpoint(self, **kwargs: object) -> TaskCheckpoint | None:
        del kwargs
        return None

    async def checkpoint(self, **kwargs: object) -> TaskCheckpoint:
        self.checkpoint_calls += 1
        return TaskCheckpoint(
            task_id=kwargs["task_id"],
            case_id=kwargs["case_id"],
            case_version=kwargs["case_version"],
            document_version_id=kwargs["document_version_id"],
            sequence_no=kwargs["sequence_no"],
            checkpoint_type=kwargs["checkpoint_type"],
            checkpoint_schema_version=kwargs["checkpoint_schema_version"],
            checkpoint_data=kwargs["checkpoint_data"],
            created_at=NOW,
        )

    async def succeed(self, **kwargs: object) -> None:
        del kwargs
        self.succeeded = True
        self.record = replace(
            self.record, status=TaskStatus.SUCCEEDED, lease_token=None
        )

    async def mark_superseded(self, **kwargs: object) -> None:
        del kwargs
        self.superseded_calls += 1

    async def retry_or_fail(self, **kwargs: object) -> RetryDecision:
        del kwargs
        self.retry_calls += 1
        return RetryDecision(
            TaskStatus.RETRY_WAIT, 1, NOW + timedelta(seconds=30), "retry"
        )


class SleepingProcessor:
    """A long inference that succeeds after ``sleep_for`` unless cancelled."""

    def __init__(self, *, sleep_for: float, succeed: bool = True) -> None:
        self._sleep_for = sleep_for
        self._succeed = succeed
        self.started = False
        self.completed = False
        self.cancelled = False
        self.cleanup_done = False

    async def process(
        self,
        task: TaskRecord,
        checkpoint: TaskCheckpoint | None,
        save_checkpoint: object,
    ) -> StageResult:
        del task, checkpoint, save_checkpoint
        self.started = True
        try:
            await asyncio.sleep(self._sleep_for)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        finally:
            self.cleanup_done = True
        self.completed = True
        return StageResult() if self._succeed else StageResult(
            WorkerOutcome.RETRY_WAIT, "provider unavailable"
        )


@pytest.mark.asyncio
async def test_inference_longer_than_lease_succeeds_with_a_working_renewer() -> None:
    tasks = LeaseTasks(lease_mode="ok")
    queue = OneShotQueue()
    # The inference outlives several heartbeat intervals; a working renewer
    # keeps the lease and the task still completes.
    processor = SleepingProcessor(sleep_for=0.06)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.SUCCEEDED
    assert processor.completed is True
    assert tasks.succeeded is True
    assert queue.archived == [queue.message.message_id]
    # Initial heartbeat plus at least one background renewal fired mid-inference.
    assert tasks.extend_calls >= 2
    assert tasks.retry_calls == 0


@pytest.mark.asyncio
async def test_lost_lease_returns_false_abandons_inflight_processor() -> None:
    tasks = LeaseTasks(lease_mode="false_after_first")
    queue = OneShotQueue()
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    # The in-flight processor was cancelled and unwound, not completed.
    assert processor.cancelled is True
    assert processor.completed is False
    assert processor.cleanup_done is True
    # No terminal / checkpoint write occurred and the delivery is not archived.
    assert tasks.succeeded is False
    assert tasks.checkpoint_calls == 0
    assert tasks.retry_calls == 0
    assert tasks.superseded_calls == 0
    assert queue.archived == []
    # The worker slot was released on the way out.
    assert tasks.slot is False


@pytest.mark.asyncio
async def test_lost_lease_raises_abandons_inflight_processor() -> None:
    tasks = LeaseTasks(lease_mode="raise_after_first")
    queue = OneShotQueue()
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert processor.cancelled is True
    assert processor.completed is False
    assert tasks.succeeded is False
    assert tasks.checkpoint_calls == 0
    assert tasks.retry_calls == 0
    assert queue.archived == []


@pytest.mark.asyncio
async def test_run_once_cancellation_stops_and_awaits_heartbeat() -> None:
    tasks = LeaseTasks(lease_mode="ok")
    queue = OneShotQueue()
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    run = asyncio.create_task(worker.run_once())
    # Wait until the processor is in flight (the worker is inside its supervised
    # wait), then cancel the whole run.
    for _ in range(200):
        if processor.started:
            break
        await asyncio.sleep(0.005)
    assert processor.started is True
    # Let a couple of heartbeats fire so the loop is genuinely running.
    await asyncio.sleep(0.03)

    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    # The in-flight processor was cancelled and fully unwound (awaited).
    assert processor.cancelled is True
    assert processor.cleanup_done is True
    # The slot was released and the heartbeat is stopped: no further renewals.
    assert tasks.slot is False
    calls_after_cancel = tasks.extend_calls
    await asyncio.sleep(0.05)
    assert tasks.extend_calls == calls_after_cancel
    # No worker child tasks are left pending (no "task was destroyed" warning).
    current = asyncio.current_task()
    leftover = [
        t for t in asyncio.all_tasks() if t is not current and not t.done()
    ]
    assert leftover == []
