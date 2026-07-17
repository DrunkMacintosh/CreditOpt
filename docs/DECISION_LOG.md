# Decision Log

## Purpose

This log records confirmed project decisions and their current validity. Proposed technology choices and unresolved SHB-specific rules belong in [Open Questions](OPEN_QUESTIONS.md), not in this log as settled decisions.

| Date | Decision | Reason | Alternatives considered | Status | Conditions that may invalidate or require review |
|---|---|---|---|---|---|
| 2026-07-17 | Use the Credit Case Digital Twin as the central domain object; chat history is not the source of truth. | Material case state must be structured, versioned, and traceable to evidence. | Conversation-centric chatbot; memo-only record | CONFIRMED | Review only if an authorized project source changes the product identity; traceability must remain preserved. |
| 2026-07-17 | Focus the initial phase mainly on stages 2–6: financing need through independent review and human approval. | This provides a bounded SME working-capital preparation and review use case. | Full credit lifecycle; intake-only prototype; post-credit monitoring first | CONFIRMED | Review when an official challenge scope or approved roadmap changes the first-phase boundary. |
| 2026-07-17 | Reserve all material credit decisions, exception dispositions, customer-request approvals, and operational authorizations for humans. | Banking decisions and sensitive actions require accountable human authority. | Autonomous decisioning; AI approval under thresholds | CONFIRMED | This boundary may be strengthened by official policy but must not be weakened without authoritative governance and explicit project direction. |
| 2026-07-17 | Preserve maker–checker separation: underwriting prepares and independent risk review challenges. | Independent challenge reduces self-review and keeps duties distinct. | Single agent prepares and clears; pooled undifferentiated agents | CONFIRMED | Review when the official SHB role and control model is supplied; separation of duties remains required. |
| 2026-07-17 | Require evidence and provenance for every material conclusion and expose unresolved gaps and uncertainty. | The case must be auditable and conclusions must be reviewable. | Uncited narrative; confidence without source lineage | CONFIRMED | May be extended with official retention or audit requirements; the core traceability requirement remains. |
| 2026-07-17 | Use deterministic tools for material calculations, explicit rules, state changes, and controlled actions. | These operations require repeatable behavior, validation, and auditability. | Free-form LLM calculation or action; unvalidated tool calls | CONFIRMED | Tool selection and thresholds may change after requirements are known; deterministic control remains. |
| 2026-07-17 | Use synthetic data only during development and demonstration, with the required visible disclaimer. | No real customer or banking information is needed for the current context and demonstration scope. | De-identified production data; real sandbox data | CONFIRMED | Review only if an authorized governance process explicitly approves another data class and its controls; no such approval currently exists. |
| 2026-07-17 | Keep model-facing application contracts provider agnostic and leave final model selection benchmark-gated. | Model quality and endpoint capabilities must be measured independently from application logic. | Bind agents directly to one provider-specific model contract | CONFIRMED | Revisit model selection when representative benchmark results are recorded; provider abstraction remains required. |
| 2026-07-17 | Treat Evidence Gap Resolution as a workflow capability rather than a separate conversational agent. | Gaps affect shared case state, dependencies, human requests, and re-analysis across roles. | Dedicated gap-chat agent; unstructured task comments | CONFIRMED | Review if a future architecture assigns a distinct service or role; the structured workflow behavior must remain. |
| 2026-07-17 | Use FPT AI Factory in Southeast Asia as the target private AI infrastructure through an hourly H100 VM and local vLLM. | The selected H100 VM supported the initially intended locally hosted, shared-model inference design. | The previously considered infrastructure option | SUPERSEDED by the managed architecture decision below | Retained as history; reconsider only if managed FPT endpoints cannot meet security, availability, capability, or cost requirements. |
| 2026-07-17 | Use Vercel for the frontend, Cloud Run for FastAPI and asynchronous CPU workers, Supabase for durable shared state, queues, private object storage, and pgvector, and FPT AI Factory only for managed inference. | This retains the full Relationship and Intake feature set without operating a GPU, keeps workflow authority outside the model, and provides durable checkpoints and resumable document processing. | FPT H100 VM with vLLM; Vercel Workflows; Supabase Edge Functions as sole backend; Fly.io long-lived workers | CONFIRMED | Review if required data residency, private networking, security controls, provider availability, benchmark quality, latency, or cost cannot be satisfied. |

## Superseded infrastructure decision detail — 2026-07-17

**Decision — SUPERSEDED:** Use an hourly FPT AI Factory H100 VM as the target private AI infrastructure.

**Selected configuration:**

- 1 × NVIDIA H100 SXM5;
- 80 GB HBM3;
- 192 GB system RAM;
- 16 CPU cores;
- Intel Xeon Platinum Processor 8462Y+;
- 3 TB local NVMe;
- Southeast Asia region; and
- hourly rental.

**Reason:**

- suitable for locally hosted open-weight LLM inference;
- supports keeping data and inference in a controlled environment;
- supports one shared model for all logical agent roles;
- provides capacity for a strong model plus KV cache and runtime overhead;
- supports benchmarking and a future horizontal-replica scaling direction; and
- aligns with the desired private-bank infrastructure concept.

**Superseded history:** The previously considered infrastructure option is retired because FPT AI Factory now provides the confirmed provider, region, and VM target. This history is retained without carrying the obsolete option into the current architecture.

**Conditions that may invalidate or require review:**

- required CUDA or container support is unavailable;
- network restrictions prevent internal API serving;
- local storage is unsuitable and no persistent alternative exists;
- the selected model cannot meet Vietnamese banking benchmarks;
- continuous-operation cost exceeds the project budget; or
- competition rules require another infrastructure provider.

No VM was provisioned. The managed architecture below supersedes this configuration before implementation. The provider-neutral application-contract principle remains valid.

## Managed architecture decision detail — 2026-07-17

**Decision — CONFIRMED:** Use the following service boundaries:

- Vercel hosts the Vietnamese Next.js frontend and does not orchestrate document processing;
- Cloud Run hosts the FastAPI API, deterministic workflow authority, provider gateway, and an asynchronous `creditops-worker` Job;
- Supabase Postgres stores the Credit Case Digital Twin, EvidenceGraph, workflow state, checkpoints, retrieval metadata, permissions metadata, and audit records;
- Supabase Queues carries durable work identifiers with bounded leases, retries, and archival;
- private Supabase Storage stores immutable originals and versioned derived artifacts, with a separate backup and restore design;
- Supabase pgvector supports case-evidence and approved-policy retrieval indexes;
- browser uploads use a backend-created upload intent, with a short-lived signed upload for normal uploads or authenticated resumable upload under Storage RLS when required, and do not pass document bodies through Vercel Functions; and
- FPT AI Factory provides managed reasoning, document, vision, embedding, and optional reranking inference only.

Cloud Run, not Supabase or FPT, owns orchestration and deterministic banking logic. Supabase is the durable source of shared state. FPT model output remains non-authoritative until schema validation and the applicable human confirmation gate.

**Candidate model direction — PROPOSED and benchmark-gated:** Qwen3-30B-A3B instruction/chat as the main reasoning candidate if an appropriate FPT endpoint is available; SaoLa3.1-medium 32B as the Vietnamese challenger; FPT.AI-KIE-v1.7 and FPT.AI-Table-Parsing-v1.1 for document extraction; Qwen2.5-VL-7B-Instruct as the complex-visual fallback; FPT.AI-e5-large compared with Vietnamese_Embedding for retrieval; and bge-reranker-v2-m3 only if measured retrieval gains justify a managed endpoint. DeepSeek-V4-Flash remains a challenger only if FPT exposes a suitable endpoint.

## Current non-decisions

The following are intentionally not decided:

- exact framework versions and whether an additional workflow library is necessary beyond the explicit state machine;
- final model, embedding model, reranker, KIE, table, or document-vision endpoint after benchmarking;
- provider regions, private networking, backup and restore settings, quotas, scaling, and monitoring configuration;
- official SHB policies, rules, checklist, roles, gates, or memo format;
- production integrations; and
- evaluation metrics and pass thresholds.

## Change discipline

Future entries should include date, decision, reason, alternatives considered, status, and invalidation conditions. If a decision is superseded, retain the original row and add a new row that references it rather than rewriting history.

## Related documents

- [Project Context](PROJECT_CONTEXT.md)
- [Product Boundaries](PRODUCT_BOUNDARIES.md)
- [Technical Direction](TECHNICAL_DIRECTION.md)
- [Open Questions](OPEN_QUESTIONS.md)
