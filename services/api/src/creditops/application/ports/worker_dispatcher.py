"""Contract for asking Cloud Run to execute the durable worker sweep."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class WorkerDispatchError(RuntimeError):
    """A worker execution could not be requested."""


class WorkerDispatchNotConfigured(WorkerDispatchError):
    """Dispatch is disabled until the managed worker is configured."""


@dataclass(frozen=True, slots=True)
class WorkerDispatchResult:
    accepted: bool
    execution_name: str | None = None


class WorkerDispatcher(Protocol):
    async def request_execution(self) -> WorkerDispatchResult: ...
