"""Committed FPT benchmark-pass registry.

A capability route may only activate in the application configuration path
(``FPTCatalog.from_configuration``) when this registry contains a PASSED
record binding the exact ``capability``, ``model_id``, ``endpoint_id``,
``route_version``, ``prompt_version`` and ``schema_version`` being activated.
Benchmark evidence is committed code — reviewed, versioned, auditable — never
runtime configuration; no environment variable can inject a record or bypass
the gate.

The registry ships EMPTY: no representative Vietnamese banking/document
benchmark has been executed yet, so every route stays DISABLED (fail closed).
To activate a route, run the evaluation harness against the live managed
endpoint (``FPTCatalog.for_benchmark_evaluation`` + ``scripts/smoke_fpt.py``
or the evaluation suite), commit the evidence artefact it produces, add the
record here in a reviewed change, and record the outcome in
``docs/DECISION_LOG.md``. Never add a speculative record.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from creditops.infrastructure.fpt.catalog import CapabilityName


class FPTBenchmarkRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: CapabilityName
    model_id: str = Field(min_length=1, max_length=200)
    endpoint_id: str = Field(min_length=1, max_length=200)
    route_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(min_length=1, max_length=100)
    passed: bool
    #: Repository-relative pointer to the committed evidence artefact.
    evidence_ref: str = Field(min_length=1, max_length=500)
    #: ISO calendar date the run was recorded (committed data, not a clock read).
    recorded_on: str = Field(min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")


#: Committed benchmark-pass records. Each row activates exactly one capability
#: route in ``FPTCatalog.from_configuration``; the evidence artefact lives under
#: ``docs/benchmarks/``. Reasoning was recorded from a live 14/14 run of the
#: synthetic Vietnamese-banking holdout against DeepSeek-V4-Flash on
#: FPT AI Factory (2026-07-18); see ``docs/DECISION_LOG.md``.
FPT_BENCHMARK_RECORDS: tuple[FPTBenchmarkRecord, ...] = (
    FPTBenchmarkRecord(
        capability="reasoning",
        model_id="DeepSeek-V4-Flash",
        endpoint_id="mkp-api.fptcloud.com",
        route_version="fpt-route-v1",
        prompt_version="intake-prompt-v1",
        schema_version="intake-schema-v1",
        passed=True,
        evidence_ref="docs/benchmarks/reasoning-DeepSeek-V4-Flash-evidence.md",
        recorded_on="2026-07-18",
    ),
)
