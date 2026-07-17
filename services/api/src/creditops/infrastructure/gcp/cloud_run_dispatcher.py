"""Fail-closed Cloud Run Job dispatch through the Google API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast
from urllib.parse import quote, urlsplit

import httpx

from creditops.application.ports.worker_dispatcher import (
    WorkerDispatcher,
    WorkerDispatchError,
    WorkerDispatchNotConfigured,
    WorkerDispatchResult,
)

TokenProvider = Callable[[], str | Awaitable[str]]


class CloudRunDispatcher(WorkerDispatcher):
    """Request one Job execution without sending task data in the request.

    A Cloud Scheduler sweep and the API can race safely: both only request a
    stateless one-message execution, while Supabase owns slot and task leases.
    """

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        job_name: str,
        token_provider: TokenProvider | None,
        client: httpx.AsyncClient | None = None,
        api_base_url: str = "https://run.googleapis.com",
    ) -> None:
        if not project_id or not location or not job_name:
            raise ValueError("Cloud Run project, location, and job are required")
        parsed = urlsplit(api_base_url)
        if parsed.scheme != "https" or parsed.hostname != "run.googleapis.com" or parsed.query:
            raise ValueError("Cloud Run API base URL must be https://run.googleapis.com")
        self._project_id = project_id
        self._location = location
        self._job_name = job_name
        self._token_provider = token_provider
        self._base_url = api_base_url.rstrip("/")
        self._client = client
        self._owns_client = client is None

    def _execution_url(self) -> str:
        return (
            f"{self._base_url}/v2/projects/{quote(self._project_id, safe='')}/locations/"
            f"{quote(self._location, safe='')}/jobs/{quote(self._job_name, safe='')}:run"
        )

    async def _token(self) -> str:
        if self._token_provider is None:
            raise WorkerDispatchNotConfigured("Cloud Run OAuth token provider is not configured")
        token = self._token_provider()
        if hasattr(token, "__await__"):
            token = await cast(Awaitable[str], token)
        if not isinstance(token, str) or not token or len(token) > 4096:
            raise WorkerDispatchNotConfigured("Cloud Run OAuth token is invalid")
        return token

    async def request_execution(self) -> WorkerDispatchResult:
        token = await self._token()
        client = self._client
        owns_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))
            owns_client = True
        try:
            try:
                response = await client.post(
                    self._execution_url(),
                    headers={"Authorization": f"Bearer {token}"},
                    json={},
                )
            except httpx.HTTPError as exc:
                raise WorkerDispatchError("Cloud Run execution request failed") from exc
            if response.status_code not in (200, 201, 202):
                raise WorkerDispatchError("Cloud Run rejected the worker execution request")
            execution_name: str | None = None
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and isinstance(body.get("name"), str):
                execution_name = body["name"]
            return WorkerDispatchResult(accepted=True, execution_name=execution_name)
        finally:
            if owns_client:
                await client.aclose()

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
