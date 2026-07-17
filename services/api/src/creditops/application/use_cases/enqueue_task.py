from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from creditops.application.ports.queue import QueuePort, TaskRepository
from creditops.domain.tasks import TaskEnvelopeV1


class TaskEnqueueError(ValueError):
    """A task cannot be placed on the durable queue."""


@dataclass(frozen=True, slots=True)
class EnqueuedTask:
    task_id: UUID
    message_id: int


class EnqueueTask:
    """Publish a task identifier after its database row already exists."""

    def __init__(self, tasks: TaskRepository, queue: QueuePort) -> None:
        self._tasks = tasks
        self._queue = queue

    async def execute(self, envelope: TaskEnvelopeV1, *, delay_seconds: int = 0) -> EnqueuedTask:
        if delay_seconds < 0 or delay_seconds > 86_400:
            raise TaskEnqueueError("queue delay is outside the bounded contract")
        task = await self._tasks.get(envelope.task_id, case_id=envelope.case_id)
        if task is None:
            raise TaskEnqueueError("task is not durable or is outside the case scope")
        if (
            task.case_version != envelope.case_version
            or task.document_version_id != envelope.document_version_id
        ):
            raise TaskEnqueueError("queue envelope does not match the durable task version")
        message_id = await self._queue.send(envelope, delay_seconds=delay_seconds)
        return EnqueuedTask(task_id=envelope.task_id, message_id=message_id)
