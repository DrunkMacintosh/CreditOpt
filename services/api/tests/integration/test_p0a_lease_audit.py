"""P0-A independent lease-safety audit for :class:`RunWorkerOnce`.

These are NEW, self-contained failure-injection tests written by an independent
auditor.  They exercise the three-layer heartbeat (task lease + worker slot +
queue visibility), the abandon-on-lost-lease contract, structured
cancellation, and the terminal/archive ordering, using deterministic fakes
(fast fake clock + tiny heartbeat interval + asyncio events) rather than real
timeouts.

Every fake defines ``extend_task_lease`` AND ``extend_worker_slot`` DIRECTLY on
its class so that ``RunWorkerOnce._own_method`` (which inspects
``type(tasks).__dict__``) actually invokes the slot-renewal layer — the
existing repo fakes omit ``extend_worker_slot`` and therefore never exercise
it.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from creditops.application.ports.queue import (
    QueueMessage,
    RetryDecision,
    StaleTaskError,
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


def _record() -> TaskRecord:
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
        idempotency_key="UPLOAD:p0a",
    )


class AuditQueue:
    """One-shot queue with an injectable ``extend_visibility`` failure.

    ``visibility_mode``:
    * ``"ok"`` -- always extends.
    * ``"raise_after_first"`` -- extends the very first heartbeat then raises a
      generic ``RuntimeError`` (a transient queue outage), never a
      ``TaskLeaseLost``.
    """

    def __init__(self, *, visibility_mode: str = "ok", events: list[str] | None = None) -> None:
        self.message = QueueMessage(7, 1, NOW, NOW, _envelope())
        self.read = False
        self.archived: list[int] = []
        self.visibility_calls = 0
        self._visibility_mode = visibility_mode
        self._events = events

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
        self.visibility_calls += 1
        if self._events is not None:
            self._events.append("visibility")
        if self._visibility_mode == "raise_after_first" and self.visibility_calls > 1:
            raise RuntimeError("queue visibility extension failed (transient)")

    async def archive(self, message_id: int) -> None:
        if self._events is not None:
            self._events.append("archive")
        self.archived.append(message_id)


class AuditTasks:
    """Task double with all three lease layers and per-layer failure injection.

    Modes for ``task_lease_mode`` / ``slot_mode``:
    * ``"ok"`` -- always renews.
    * ``"false_after_first"`` -- first renewal True, thereafter False.
    * ``"raise_after_first"`` -- first renewal True, thereafter TaskLeaseLost.

    ``checkpoint_raises`` / ``succeed_raises`` / ``retry_raises`` inject the
    database fence rejections (StaleTaskError / TaskLeaseLost) that a stale
    lease_token or case_version would produce.
    """

    def __init__(
        self,
        *,
        task_lease_mode: str = "ok",
        slot_mode: str = "ok",
        checkpoint_error: Exception | None = None,
        succeed_error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.record = _record()
        self._task_lease_mode = task_lease_mode
        self._slot_mode = slot_mode
        self._checkpoint_error = checkpoint_error
        self._succeed_error = succeed_error
        self._events = events
        self.slot = False
        self.task_extend_calls = 0
        self.slot_extend_calls = 0
        self.checkpoint_calls = 0
        self.succeed_calls = 0
        self.superseded_calls = 0
        self.retry_calls = 0
        self.reclaim_calls = 0
        self.released = False

    async def acquire_worker_slot(self, **kwargs: object) -> bool:
        del kwargs
        if self.slot:
            return False
        self.slot = True
        return True

    async def release_worker_slot(self, **kwargs: object) -> None:
        del kwargs
        self.slot = False
        self.released = True

    async def extend_task_lease(self, **kwargs: object) -> bool:
        del kwargs
        self.task_extend_calls += 1
        if self._events is not None:
            self._events.append("task_lease")
        if self.task_extend_calls == 1:
            return True
        if self._task_lease_mode == "false_after_first":
            return False
        if self._task_lease_mode == "raise_after_first":
            raise TaskLeaseLost("task lease reclaimed mid-inference")
        return True

    async def extend_worker_slot(self, **kwargs: object) -> bool:
        del kwargs
        self.slot_extend_calls += 1
        if self._events is not None:
            self._events.append("worker_slot")
        if self.slot_extend_calls == 1:
            return True
        if self._slot_mode == "false_after_first":
            return False
        if self._slot_mode == "raise_after_first":
            raise TaskLeaseLost("worker slot reclaimed mid-inference")
        return True

    async def reclaim_stranded(self, **kwargs: object) -> tuple[UUID, ...]:
        del kwargs
        self.reclaim_calls += 1
        return ()

    async def claim(self, **kwargs: object) -> TaskRecord | None:
        token = kwargs["lease_token"]
        assert isinstance(token, UUID)
        if self.record.status not in (TaskStatus.PENDING, TaskStatus.RETRY_WAIT):
            return None
        self.record = replace(self.record, status=TaskStatus.RUNNING, lease_token=token)
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
        if self._events is not None:
            self._events.append("checkpoint")
        if self._checkpoint_error is not None:
            raise self._checkpoint_error
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
        self.succeed_calls += 1
        if self._events is not None:
            self._events.append("succeed")
        if self._succeed_error is not None:
            raise self._succeed_error
        self.record = replace(self.record, status=TaskStatus.SUCCEEDED, lease_token=None)

    async def mark_superseded(self, **kwargs: object) -> None:
        del kwargs
        self.superseded_calls += 1

    async def retry_or_fail(self, **kwargs: object) -> RetryDecision:
        del kwargs
        self.retry_calls += 1
        if self._events is not None:
            self._events.append("retry")
        return RetryDecision(
            TaskStatus.RETRY_WAIT, 1, NOW + timedelta(seconds=30), "retry"
        )


class SleepingProcessor:
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


# --- (1) inference outlives lease: all three layers renew, no second worker steals


@pytest.mark.asyncio
async def test_long_inference_renews_all_three_layers_and_second_worker_blocked() -> None:
    tasks = AuditTasks()
    queue = AuditQueue()
    processor = SleepingProcessor(sleep_for=0.06)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    # A SECOND worker sharing the single global slot must be shut out for the
    # whole in-flight inference: it cannot steal the leased task.
    thief = RunWorkerOnce(
        tasks, queue, SleepingProcessor(sleep_for=0.06), clock=lambda: NOW,
        heartbeat_interval_seconds=0.01,
    )

    winner, loser = await asyncio.gather(worker.run_once(), thief.run_once())

    outcomes = sorted([winner.outcome, loser.outcome])
    assert outcomes == [WorkerOutcome.NO_SLOT, WorkerOutcome.SUCCEEDED]
    assert processor.completed is True
    assert tasks.succeed_calls == 1
    assert queue.archived == [queue.message.message_id]
    # All THREE heartbeat layers renewed at least twice (initial + >=1 beat).
    assert tasks.task_extend_calls >= 2
    assert tasks.slot_extend_calls >= 2
    assert queue.visibility_calls >= 2
    assert tasks.retry_calls == 0


# --- (2) task-lease renewal fails while slot+visibility would renew -> abandon


@pytest.mark.asyncio
async def test_task_lease_lost_abandons_even_when_slot_and_visibility_healthy() -> None:
    tasks = AuditTasks(task_lease_mode="false_after_first", slot_mode="ok")
    queue = AuditQueue(visibility_mode="ok")
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert processor.cancelled is True and processor.completed is False
    # No terminal / checkpoint / retry write, no archive: delivery stays recoverable.
    assert tasks.succeed_calls == 0
    assert tasks.checkpoint_calls == 0
    assert tasks.retry_calls == 0
    assert tasks.superseded_calls == 0
    assert queue.archived == []
    assert tasks.released is True
    # task lease is renewed FIRST, so the slot renewal never even runs a 2nd beat.
    assert tasks.slot_extend_calls <= tasks.task_extend_calls


# --- (4) worker-slot renewal fails -> abandon (task lease still healthy)


@pytest.mark.asyncio
async def test_worker_slot_lost_abandons_inflight_processor() -> None:
    tasks = AuditTasks(task_lease_mode="ok", slot_mode="false_after_first")
    queue = AuditQueue(visibility_mode="ok")
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert processor.cancelled is True and processor.completed is False
    assert tasks.succeed_calls == 0
    assert tasks.checkpoint_calls == 0
    assert tasks.retry_calls == 0
    assert queue.archived == []
    assert tasks.released is True


@pytest.mark.asyncio
async def test_worker_slot_raise_abandons_inflight_processor() -> None:
    tasks = AuditTasks(task_lease_mode="ok", slot_mode="raise_after_first")
    queue = AuditQueue(visibility_mode="ok")
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert processor.cancelled is True
    assert tasks.succeed_calls == 0
    assert queue.archived == []


# --- (3) queue-visibility renewal fails -> documented actual behavior


@pytest.mark.asyncio
async def test_visibility_renewal_failure_is_safe_no_terminal_no_archive() -> None:
    """A transient queue-visibility outage must never yield a terminal/duplicate.

    ACTUAL behavior (documented, not asserted-correct-by-name): a generic
    ``extend_visibility`` failure is NOT mapped to ``TaskLeaseLost``; it unwinds
    through ``except Exception`` and collapses to a ``retry_or_fail`` durable
    write (RETRY_WAIT), discarding the in-flight work.  This is SAFE (no
    terminal SUCCEED, no archive, no duplicate side effect) but asymmetric with
    the task/slot layers, which fail-closed to STALE with NO write.  See
    FINDING P0A-1.
    """
    tasks = AuditTasks(task_lease_mode="ok", slot_mode="ok")
    queue = AuditQueue(visibility_mode="raise_after_first")
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()

    # The safety-critical invariants hold regardless of how the failure is mapped:
    assert tasks.succeed_calls == 0
    assert tasks.superseded_calls == 0
    assert queue.archived == []
    assert processor.completed is False
    assert tasks.released is True
    # Documented actual outcome: transient visibility failure -> a retry write.
    assert result.outcome is WorkerOutcome.RETRY_WAIT
    assert tasks.retry_calls == 1


# --- (5) lease_token/attempt changed mid-execution -> stale checkpoint fenced


@pytest.mark.asyncio
async def test_stale_lease_token_cannot_checkpoint() -> None:
    """A checkpoint under a reclaimed lease is rejected (StaleTaskError) and the
    worker abandons without a terminal write or archive."""

    class CheckpointingProcessor:
        def __init__(self) -> None:
            self.reached_after_checkpoint = False

        async def process(self, task, checkpoint, save_checkpoint):
            del task, checkpoint
            await save_checkpoint("PARSED", {"ok": True})
            # If the fence worked, control never reaches here.
            self.reached_after_checkpoint = True
            return StageResult()

    tasks = AuditTasks(
        checkpoint_error=StaleTaskError("task or version no longer current")
    )
    queue = AuditQueue()
    processor = CheckpointingProcessor()
    # Large heartbeat so the checkpoint fence (not a background beat) drives the outcome.
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=100.0
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert processor.reached_after_checkpoint is False
    assert tasks.checkpoint_calls == 1
    assert tasks.succeed_calls == 0
    assert tasks.retry_calls == 0
    assert queue.archived == []


# --- (6) case_version changed mid-execution -> terminal write fenced, no archive


@pytest.mark.asyncio
async def test_stale_case_version_terminal_write_is_fenced_and_not_archived() -> None:
    tasks = AuditTasks(
        succeed_error=TaskLeaseLost("task lease is no longer owned")
    )
    queue = AuditQueue()
    processor = SleepingProcessor(sleep_for=0.0, succeed=True)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=100.0
    )

    result = await worker.run_once()

    # succeed() was ATTEMPTED but the DB fence rejected it; the message must NOT
    # be archived on a fenced terminal write (redelivery stays recoverable).
    assert result.outcome is WorkerOutcome.STALE
    assert tasks.succeed_calls == 1
    assert queue.archived == []


# --- (7) cancellation during model call -> heartbeat stopped AND awaited


@pytest.mark.asyncio
async def test_cancellation_stops_and_awaits_heartbeat_no_leak() -> None:
    tasks = AuditTasks()
    queue = AuditQueue()
    processor = SleepingProcessor(sleep_for=5.0)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    run = asyncio.create_task(worker.run_once())
    for _ in range(200):
        if processor.started:
            break
        await asyncio.sleep(0.005)
    assert processor.started is True
    await asyncio.sleep(0.03)

    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    assert processor.cancelled is True
    assert processor.cleanup_done is True
    assert tasks.slot is False
    calls_after_cancel = tasks.task_extend_calls
    slot_after_cancel = tasks.slot_extend_calls
    await asyncio.sleep(0.05)
    # No leaked background renewal on any layer after the run ended.
    assert tasks.task_extend_calls == calls_after_cancel
    assert tasks.slot_extend_calls == slot_after_cancel
    current = asyncio.current_task()
    leftover = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    assert leftover == []


# --- (8) processor exception -> retry transition, heartbeat cleaned, no double terminal


@pytest.mark.asyncio
async def test_processor_exception_retries_without_double_terminal() -> None:
    class ExplodingProcessor:
        async def process(self, task, checkpoint, save_checkpoint):
            del task, checkpoint, save_checkpoint
            raise ValueError("provider blew up mid-inference")

    tasks = AuditTasks()
    queue = AuditQueue()
    worker = RunWorkerOnce(
        tasks, queue, ExplodingProcessor(), clock=lambda: NOW,
        heartbeat_interval_seconds=0.01,
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.RETRY_WAIT
    assert tasks.retry_calls == 1
    assert tasks.succeed_calls == 0  # no terminal success on an exception path
    assert queue.archived == []  # RETRY_WAIT does not archive
    assert tasks.released is True
    # Heartbeat fully cleaned up: no leftover renewal tasks.
    current = asyncio.current_task()
    leftover = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    assert leftover == []


# --- (9) renewal exception right after a checkpoint is not swallowed-then-committed


@pytest.mark.asyncio
async def test_renewal_failure_after_checkpoint_is_not_committed() -> None:
    class CheckpointThenContinue:
        async def process(self, task, checkpoint, save_checkpoint):
            del task, checkpoint
            # save_checkpoint persists the checkpoint, THEN renews the lease.
            # The renewal raises TaskLeaseLost; it must propagate, not be
            # swallowed followed by a terminal success.
            await save_checkpoint("PARSED", {"ok": True})
            return StageResult()

    # task_lease raises on the 2nd call (initial renew ok, save_checkpoint renew raises).
    tasks = AuditTasks(task_lease_mode="raise_after_first")
    queue = AuditQueue()
    worker = RunWorkerOnce(
        tasks, queue, CheckpointThenContinue(), clock=lambda: NOW,
        heartbeat_interval_seconds=100.0,
    )

    result = await worker.run_once()

    assert result.outcome is WorkerOutcome.STALE
    assert tasks.checkpoint_calls == 1  # checkpoint persisted (resumable) ...
    assert tasks.succeed_calls == 0  # ... but NO terminal commit after lost lease
    assert queue.archived == []


# --- (11) success path -> heartbeat stops before terminal+archive, no post-archive renewal


@pytest.mark.asyncio
async def test_success_ordering_no_renewal_after_archive() -> None:
    events: list[str] = []
    tasks = AuditTasks(events=events)
    queue = AuditQueue(events=events)
    processor = SleepingProcessor(sleep_for=0.05)
    worker = RunWorkerOnce(
        tasks, queue, processor, clock=lambda: NOW, heartbeat_interval_seconds=0.01
    )

    result = await worker.run_once()
    assert result.outcome is WorkerOutcome.SUCCEEDED

    assert "succeed" in events and "archive" in events
    # succeed strictly precedes archive.
    assert events.index("succeed") < events.index("archive")
    archive_pos = len(events) - 1 - events[::-1].index("archive")
    renewal_names = {"task_lease", "worker_slot", "visibility"}
    # No renewal of ANY layer occurs after the message is archived.
    assert not any(e in renewal_names for e in events[archive_pos + 1 :])

    # And no renewal fires after run_once returns (heartbeat cancelled+awaited).
    task_after = tasks.task_extend_calls
    slot_after = tasks.slot_extend_calls
    vis_after = queue.visibility_calls
    await asyncio.sleep(0.05)
    assert tasks.task_extend_calls == task_after
    assert tasks.slot_extend_calls == slot_after
    assert queue.visibility_calls == vis_after


# --- (10) single global slot serializes redelivery -> no duplicate terminal


@pytest.mark.asyncio
async def test_single_slot_serializes_concurrent_redelivery() -> None:
    tasks = AuditTasks()
    queue = AuditQueue()

    def make(worker_id: UUID) -> RunWorkerOnce:
        return RunWorkerOnce(
            tasks, queue, SleepingProcessor(sleep_for=0.02), worker_id=worker_id,
            clock=lambda: NOW, heartbeat_interval_seconds=0.005,
        )

    a, b = await asyncio.gather(
        make(uuid4()).run_once(), make(uuid4()).run_once()
    )
    # Exactly one terminal success + one archive across two concurrent deliveries.
    assert sorted([a.outcome, b.outcome]) == [
        WorkerOutcome.NO_SLOT,
        WorkerOutcome.SUCCEEDED,
    ]
    assert tasks.succeed_calls == 1
    assert queue.archived == [queue.message.message_id]
