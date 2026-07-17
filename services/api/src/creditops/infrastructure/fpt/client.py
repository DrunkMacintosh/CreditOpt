from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from creditops.application.ports.model_gateway import InferenceUnavailableError
from creditops.infrastructure.fpt.catalog import CapabilityName, FPTCatalog


class FPTClient:
    """Minimal HTTP adapter for one configured FPT endpoint.

    The provider protocol is deliberately kept at JSON level because exact FPT
    endpoint shapes are an open question.  No other provider or model can be
    selected by this class.
    """

    def __init__(
        self,
        catalog: FPTCatalog,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.catalog = catalog
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def infer(
        self, capability: CapabilityName, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        try:
            config = self.catalog.config_for(capability)
        except ValueError as exc:
            raise InferenceUnavailableError(str(exc)) from exc
        headers = {
            "Authorization": f"Bearer {config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-FPT-Endpoint-ID": config.endpoint_id,
            "X-FPT-Model-ID": config.model_id,
        }
        try:
            response = await self._client.post(
                config.endpoint_url,
                headers=headers,
                json={"model": config.model_id, "input": dict(payload)},
            )
        except httpx.HTTPError as exc:
            raise InferenceUnavailableError("FPT request failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise InferenceUnavailableError(f"FPT endpoint returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise InferenceUnavailableError("FPT response was not JSON") from exc
        if not isinstance(body, Mapping):
            raise InferenceUnavailableError("FPT response must be a JSON object")
        return body
