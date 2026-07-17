from __future__ import annotations

import httpx
import pytest

from creditops.application.ports.worker_dispatcher import (
    WorkerDispatchError,
    WorkerDispatchNotConfigured,
)
from creditops.infrastructure.gcp.cloud_run_dispatcher import CloudRunDispatcher


@pytest.mark.asyncio
async def test_dispatch_requests_job_without_task_payload() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202, json={"name": "jobs/run-1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    dispatcher = CloudRunDispatcher(
        project_id="synthetic-project",
        location="asia-southeast1",
        job_name="creditops-worker",
        token_provider=lambda: "oauth-token",
        client=client,
    )
    result = await dispatcher.request_execution()
    assert result.accepted is True
    assert requests[0].url.path.endswith("/jobs/creditops-worker:run")
    assert requests[0].headers["authorization"] == "Bearer oauth-token"
    assert requests[0].content == b"{}"
    await client.aclose()


@pytest.mark.asyncio
async def test_dispatch_fails_closed_without_oauth_token() -> None:
    dispatcher = CloudRunDispatcher(
        project_id="synthetic-project",
        location="asia-southeast1",
        job_name="creditops-worker",
        token_provider=None,
    )
    with pytest.raises(WorkerDispatchNotConfigured):
        await dispatcher.request_execution()


@pytest.mark.asyncio
async def test_dispatch_rejects_non_success_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(403)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    dispatcher = CloudRunDispatcher(
        project_id="synthetic-project",
        location="asia-southeast1",
        job_name="creditops-worker",
        token_provider=lambda: "oauth-token",
        client=client,
    )
    with pytest.raises(WorkerDispatchError):
        await dispatcher.request_execution()
    await client.aclose()
