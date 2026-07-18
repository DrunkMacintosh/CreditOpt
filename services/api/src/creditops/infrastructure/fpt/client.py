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
        max_response_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        if max_response_bytes <= 0 or max_response_bytes > 50 * 1024 * 1024:
            raise ValueError("max_response_bytes is outside the bounded range")
        self.catalog = catalog
        self._max_response_bytes = max_response_bytes
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
            async with self._client.stream(
                "POST",
                config.endpoint_url,
                headers=headers,
                json={"model": config.model_id, "input": dict(payload)},
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise InferenceUnavailableError(
                        f"FPT endpoint returned HTTP {response.status_code}"
                    )
                declared_length = response.headers.get("content-length")
                if declared_length is not None:
                    try:
                        declared_bytes = int(declared_length)
                    except ValueError as exc:
                        raise InferenceUnavailableError("FPT response length was invalid") from exc
                    if declared_bytes > self._max_response_bytes:
                        raise InferenceUnavailableError("FPT response exceeded the byte limit")
                body_bytes = bytearray()
                async for chunk in response.aiter_bytes(64 * 1024):
                    body_bytes.extend(chunk)
                    if len(body_bytes) > self._max_response_bytes:
                        raise InferenceUnavailableError("FPT response exceeded the byte limit")
        except httpx.HTTPError as exc:
            raise InferenceUnavailableError("FPT request failed") from exc
        try:
            import json

            body = json.loads(body_bytes)
        except ValueError as exc:
            raise InferenceUnavailableError("FPT response was not JSON") from exc
        if not isinstance(body, Mapping):
            raise InferenceUnavailableError("FPT response must be a JSON object")
        return body
