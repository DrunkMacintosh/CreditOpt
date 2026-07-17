from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import httpx
import pytest

from creditops.application.ports.model_gateway import (
    InferenceValidationError,
    ReasonRequest,
)
from creditops.infrastructure.fpt.catalog import FPTCatalog, FPTCapabilityConfig
from creditops.infrastructure.fpt.client import FPTClient
from creditops.infrastructure.fpt.gateway import FPTInferenceGateway


class FakeTransport:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self.responses = responses
        self.called_endpoint_ids: list[str] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.called_endpoint_ids.append(request.headers["x-fpt-endpoint-id"])
        body = self.responses.pop(0)
        return httpx.Response(200, json=body, request=request)


def _gateway(transport: FakeTransport) -> FPTInferenceGateway:
    config = FPTCapabilityConfig(
        capability="reasoning",
        endpoint_id="reasoning-1",
        model_id="qwen3-benchmark-gated",
        endpoint_url="https://fpt.example/v1/infer",
        api_key="test-key",
    )
    catalog = FPTCatalog(capabilities={"reasoning": config})
    client = FPTClient(catalog, transport=httpx.MockTransport(transport))
    return FPTInferenceGateway(catalog, client, max_attempts=2)


@pytest.mark.asyncio
async def test_invalid_schema_retries_same_pinned_endpoint() -> None:
    transport = FakeTransport([{"output": {"unexpected": True}}, {"output": {"unexpected": True}}])
    gateway = _gateway(transport)
    request = ReasonRequest(
        correlation_id="corr-1",
        case_id=uuid4(),
        document_version_id=uuid4(),
        content="Nội dung tài liệu",
        response_schema={"type": "object", "required": ["answer"]},
    )
    with pytest.raises(InferenceValidationError):
        await gateway.reason(request)
    assert transport.called_endpoint_ids == ["reasoning-1", "reasoning-1"]


@pytest.mark.asyncio
async def test_valid_response_contains_provider_and_model_identity() -> None:
    transport = FakeTransport([{"output": {"answer": "Đã trích xuất có căn cứ"}, "usage": {"input_tokens": 4}}])
    gateway = _gateway(transport)
    request = ReasonRequest(
        correlation_id="corr-2",
        case_id=uuid4(),
        document_version_id=uuid4(),
        content="Nội dung tài liệu",
        response_schema={"type": "object", "required": ["answer"]},
    )
    result = await gateway.reason(request)
    assert result.provider == "FPT"
    assert result.endpoint_id == "reasoning-1"
    assert result.model_id == "qwen3-benchmark-gated"
    assert result.payload["answer"] == "Đã trích xuất có căn cứ"
