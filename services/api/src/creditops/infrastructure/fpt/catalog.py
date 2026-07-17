from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

CapabilityName = Literal["reasoning", "kie", "table", "vision", "embedding"]


class FPTCapabilityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: CapabilityName
    endpoint_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    endpoint_url: str = Field(min_length=1, max_length=2_000)
    api_key: SecretStr

    @field_validator("endpoint_url")
    @classmethod
    def https_without_query(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme.lower() != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            raise ValueError("FPT endpoint URL must be an HTTPS URL without query or fragment")
        return value.rstrip("/")

    @field_validator("endpoint_id", "model_id")
    @classmethod
    def explicit_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or normalized.casefold() in {"auto", "default", "latest"}:
            raise ValueError("FPT endpoint and model identifiers must be explicit")
        return normalized

    @field_validator("api_key")
    @classmethod
    def non_empty_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("FPT API key must be configured")
        return value


class FPTCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capabilities: Mapping[CapabilityName, FPTCapabilityConfig]
    route_version: str = Field(default="fpt-route-v1", min_length=1)
    prompt_version: str = Field(default="intake-prompt-v1", min_length=1)
    schema_version: str = Field(default="intake-schema-v1", min_length=1)

    def config_for(self, capability: CapabilityName) -> FPTCapabilityConfig:
        config = self.capabilities.get(capability)
        if config is None or config.capability != capability:
            raise ValueError(f"FPT capability is not configured: {capability}")
        return config

    @classmethod
    def from_environment(cls) -> FPTCatalog:
        """Load only explicitly configured capabilities; never guesses IDs."""

        api_key = os.environ.get("FPT_API_KEY", "")
        capabilities: dict[CapabilityName, FPTCapabilityConfig] = {}
        for capability in ("reasoning", "kie", "table", "vision", "embedding"):
            prefix = f"FPT_{capability.upper()}"
            endpoint = os.environ.get(f"{prefix}_ENDPOINT_URL")
            endpoint_id = os.environ.get(f"{prefix}_ENDPOINT_ID")
            model_id = os.environ.get(f"{prefix}_MODEL_ID")
            if not endpoint and not endpoint_id and not model_id:
                continue
            if not endpoint or not endpoint_id or not model_id or not api_key:
                raise ValueError(f"incomplete FPT {capability} configuration")
            capabilities[capability] = FPTCapabilityConfig(
                capability=capability,
                endpoint_id=endpoint_id,
                model_id=model_id,
                endpoint_url=endpoint,
                api_key=SecretStr(api_key),
            )
        return cls(capabilities=capabilities)
