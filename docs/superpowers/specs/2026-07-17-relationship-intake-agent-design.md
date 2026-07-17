# Relationship and Intake Agent Design

**Project:** SHB CreditOps EvidenceGraph  
**Design status:** Approved in conversation on 2026-07-17  
**Implementation status:** Not implemented  
**Initial interface language:** Vietnamese only

## 1. Purpose

This specification defines the first production-oriented vertical slice of SHB CreditOps EvidenceGraph: the Relationship and Intake Agent and the shared evidence foundation it requires.

The release accepts a Vietnamese SME working-capital case through the normal upload interface, preserves and analyzes every document, requires an assigned intake officer to confirm every extracted fact document by document, records conflicts and evidence gaps, and produces a versioned handoff for later specialist review.

The central product object is the Credit Case Digital Twin. Chat history is not a source of case truth.

## 2. Status classifications

### CONFIRMED

- The product concerns preparation and independent review of SME working-capital credit cases.
- The Relationship and Intake Agent is the first specialist to implement and test.
- The full product vision retains six bounded logical roles.
- The interface for this release is Vietnamese only.
- All supported document families are included in the intake design rather than limiting the product to one family.
- Every extracted fact must be explicitly dispositioned by the assigned intake officer.
- Confirmation occurs document by document before confirmed facts enter authoritative case state.
- Conflicts are surfaced immediately.
- Evidence gaps are shown progressively as provisional items and finalized only after the officer marks the upload set complete.
- Vercel hosts only the Vietnamese frontend; it does not orchestrate document processing.
- Cloud Run hosts the FastAPI API, deterministic workflow authority, provider gateway, and an asynchronous `creditops-worker` Job.
- Supabase PostgreSQL, Queues, private Storage, and pgvector hold shared state, checkpoints, durable work, documents, retrieval metadata, and audit records.
- FPT AI Factory supplies managed inference only; the product does not require a project-operated GPU or vLLM server.
- Browser document uploads use a backend-created upload intent with either a short-lived signed upload or an authenticated resumable upload protected by Storage RLS; document bodies do not pass through Vercel Functions.
- The earlier FPT H100 VM and locally hosted vLLM design is superseded before implementation.
- Initial specialization uses a benchmark-selected base model, role instructions, authorized tools, schemas, and retrieval rather than fine-tuning.
- Any later fine-tuning is benchmark-gated and limited to a measured, stable task failure.
- Development and evaluation use fully invented documents and identities. No preloaded case, seeded answers, or demo-only execution path appears in the product.
- The assigned intake officer alone may confirm or correct extracted facts for the case.

### PROPOSED

- Next.js, React, and TypeScript implementation details on Vercel; FastAPI and Pydantic implementation details on Cloud Run; and a provider-neutral structured model gateway.
- Explicit relational evidence-edge records in PostgreSQL rather than a separate graph database in the first release.
- A deterministic intake state machine rather than an autonomous agent loop.
- Two bounded retrieval paths: case-evidence RAG and approved policy/checklist RAG.
- PDF, PNG, JPEG, DOCX, and XLSX as the initial accepted file families, subject to safe parsing and size limits.
- A benchmark candidate stack consisting of Qwen3-30B-A3B instruction/chat for main reasoning if available, SaoLa3.1-medium 32B as a Vietnamese challenger, FPT.AI-KIE-v1.7, FPT.AI-Table-Parsing-v1.1, Qwen2.5-VL-7B-Instruct, FPT.AI-e5-large compared with Vietnamese_Embedding, and optional bge-reranker-v2-m3 only when measured gains justify it.

### ASSUMPTION

- The assigned intake officer represents the conceptual relationship/intake function; the official SHB role name and delegation are unavailable.
- Vietnamese document families listed in this specification are sufficient for initial product evaluation but are not an official SHB checklist.
- FPT managed endpoints will expose or be wrapped by a controlled backend adapter with equivalent structured request and response contracts.

### OPEN QUESTION

- The final reasoning, KIE, table, embedding, reranker, and document-vision endpoints after benchmark evaluation.
- Exact FPT endpoint identifiers, instruction/chat capability, regional availability, quotas, retention terms, private connectivity, and monitoring.
- Vercel, Supabase, Cloud Run, and FPT deployment regions, data-residency approval, cross-border data flows, backup and restore controls, identity integration, and security acceptance.
- Official SHB document checklists, policy corpus, role names, state names, retention rules, access model, and memo format.
- Production data authorization and security acceptance. The current project remains synthetic-only and cannot claim production readiness.
- Exact file-size, page-count, concurrency, latency, and evaluation thresholds; these must be benchmarked and recorded before release acceptance.

### OUT OF SCOPE

- Credit approval, rejection, scoring, or recommendation.
- Final legal determinations, policy waivers, or exception approvals.
- Production KYC, AML, CIC, collateral valuation, LOS, or ACAS integrations.
- Customer communication without explicit human approval.
- Contract generation or signing, disbursement, post-credit monitoring, collections, or recovery.
- Fine-tuning policies or current banking rules into model weights.
- Claims of production readiness, regulatory compliance, security certification, or SHB approval.

## 3. Product principles

1. Evidence before narrative: every material item must point to an immutable document version and addressable source location.
2. Human-confirmed case state: model output is a candidate until the assigned intake officer dispositions it.
3. Deterministic authority: permissions, state changes, validations, versioning, and controlled actions remain outside free-form model generation.
4. Fail closed: unavailable models, invalid schemas, missing citations, and retrieval failure produce visible stopped or manual-review states.
5. Preserve history: corrections and reruns create new records or versions and never erase original candidates, prior facts, or audit events.
6. Least privilege: each user and service receives only the case scope and actions needed for its function.
7. No multi-agent theatre: a logical role must have a distinct duty, context, tool set, permission boundary, or output contract.

## 4. Architecture

```text
Vietnamese Next.js interface on Vercel
  -> FastAPI application API on Cloud Run
  -> deterministic intake workflow and authorization
  -> Supabase PostgreSQL, Queues, Storage, and pgvector
  -> Cloud Run `creditops-worker` Job
  -> document ingestion, retrieval, and Intake Agent execution
  -> provider-neutral model gateway
  -> FPT managed inference endpoints
```

### 4.1 Frontend

The browser communicates with the Cloud Run application API for all case and workflow actions. It never receives model credentials, Supabase service-role credentials, or FPT credentials and never calls an FPT endpoint directly.

For a document upload, the API validates case authority and creates an expiring `UploadIntent` containing the case, officer, object key, allowed type, and size ceiling. The browser receives either a signed upload operation for a normal upload or an authenticated resumable-upload contract protected by Storage RLS. It sends the document body directly to private Supabase Storage, then asks the API to verify the object against the intent and register its immutable document version.

The interface is case-centered and supports upload, processing status, document confirmation, conflicts, gaps, intake completion, handoff, and audit inspection. Chat is not required for the first release.

### 4.2 Application backend

The FastAPI backend on Cloud Run owns authentication-token validation, authorization, assigned-officer enforcement, case state transitions, document registration, workflow orchestration, task dispatch, model routing, retrieval, schema validation, confirmation, gap finalization, handoff generation, and audit events.

Browser-facing requests do not remain open for full document processing. The API creates a durable task and returns an asynchronous status contract.

### 4.3 Intake workflow

The intake process is an explicit deterministic state machine. Model output may propose classifications and facts but cannot transition a document to `CONFIRMED`, finalize the case, close a gap, or authorize communication.

Supabase Queues carries task identifiers and attempt metadata. One `creditops-worker` Cloud Run Job execution claims one leased task in the first release, checks that its input case and document versions remain current, processes one bounded stage or resumable sequence, writes its output and checkpoint durably, and acknowledges the queue message only after success. Queue messages never contain document bodies or credentials.

The API requests a worker execution after enqueueing. Cloud Scheduler also requests one execution every minute; an execution with no eligible work exits successfully. Cloud Run platform retries are disabled for the first release because attempt count, bounded retry eligibility, failure reason, and terminal status are stored in Supabase. Parallel executions remain disabled until one-at-a-time correctness tests pass.

### 4.4 Model gateway

The gateway exposes provider-neutral structured contracts for reasoning, KIE, table extraction, vision, embeddings, and optional reranking. It records endpoint and model identity, role, prompt version, schema version, request metadata, latency, validation outcome, and usage. It has no hidden public-model fallback. If the configured FPT endpoint is unavailable, processing pauses visibly.

### 4.5 Storage

Supabase PostgreSQL is authoritative for structured case state, workflow checkpoints, EvidenceGraph records, retrieval metadata, and audit. Private Supabase Storage holds immutable content-addressed originals and separately versioned derived OCR text, page images, and safe renderings. Model candidates and officer corrections remain structured, versioned records rather than changes to source objects.

Database backup does not substitute for object backup. Object versioning, backup, restore testing, retention, and deletion controls must be approved separately before real banking data is permitted.

### 4.6 EvidenceGraph

The first release uses PostgreSQL entities plus explicit typed edge records. This preserves graph-like traversal while avoiding a second database before access patterns and scale justify it.

### 4.7 Deployment and service identity

Vercel, Cloud Run, Supabase, and FPT each receive separate least-privilege identities. Frontend environment variables contain no privileged keys. Cloud Run is the only component authorized to use Supabase service credentials or FPT credentials. Provider region, private connectivity, egress control, and workforce identity integration are release gates rather than assumptions.

### 4.8 Processing checkpoints

The default document path is `REGISTERED -> SECURITY_VALIDATED -> PARSED -> CLASSIFIED -> EXTRACTED -> INDEXED -> READY_FOR_OFFICER_REVIEW`. A task may enter `RETRY_WAIT`, `FAILED_MANUAL_REVIEW`, or `SUPERSEDED`. Retries resume from the latest valid checkpoint, and stale work cannot write to a newer case or document version.

## 5. Dual RAG design

### 5.1 Case-evidence RAG

Case-evidence retrieval searches only the current user's authorized case. It combines structured filters, lexical retrieval, vector retrieval, and optional reranking. Results retain document identifier, version, page, source region, passage, retrieval score, and reranking score.

It supports cross-document comparison, conflict detection, bounded case questions, and evidence-backed gap rationale. Unconfirmed candidates remain clearly separated from confirmed facts.

### 5.2 Policy/checklist RAG

Policy retrieval accepts only approved, versioned sources with source type, owner, effective date, expiry or supersession status, and access controls. It returns exact citations and distinguishes source text from model interpretation.

The subsystem abstains if no authorized corpus exists, no applicable passage is found, or sources conflict. Retrieval failure must never be interpreted as a statement that no policy applies. The capability remains inactive until an authorized corpus is available.

### 5.3 Retrieval authority boundary

Retrieved text is untrusted evidence. It cannot confirm a fact, grant a permission, change workflow state, close a gap, authorize a customer request, or make a credit decision.

The default retrieval path uses Supabase PostgreSQL filters, lexical search, and pgvector embeddings. A reranker is not required for the first deployment and is enabled only if held-out Vietnamese banking tests show a material citation-precision or evidence-recall gain that outweighs added latency and cost.

## 6. Supported document scope

The product supports a complete Vietnamese SME working-capital intake pack, including:

- credit request and requested structure;
- enterprise registration and authority documents;
- business and working-capital plans;
- purchase and sales contracts, purchase orders, and invoices;
- financial statements and tax declarations;
- bank statements, receivable/payable ageing, and debt schedules; and
- collateral ownership, legal, and controlled valuation-reference documents.

These families are product-oriented categories, not an official SHB checklist. Each family receives isolated tests before the combined case is evaluated.

## 7. Intake workflow

### 7.1 Create case

The assigned intake officer records the financing need, requested amount, purpose, term, expected use date, proposed repayment source, and proposed collateral. Missing fields remain missing.

### 7.2 Upload and secure document

The system validates extension and detected type, size, page count, decompression limits, and malware status. It calculates a content hash, identifies exact duplicates, preserves the immutable original, and creates a document version.

### 7.3 Parse, classify, and extract

Deterministic parsers and OCR produce addressable page content. The Intake Agent proposes the document family and candidate facts through a schema. Every candidate includes its document version, page, source region, method, and confidence.

### 7.4 Confirm document

The assigned intake officer views the original page and candidate fields together. Every field receives exactly one disposition:

- accepted;
- corrected;
- absent from the source; or
- unreadable or not reliably determinable.

A correction preserves the candidate and records the human-confirmed replacement, rationale when required, actor, timestamp, and input version. A document becomes `CONFIRMED` only when all candidates are dispositioned.

### 7.5 Update case state

Only confirmed facts enter authoritative case state. Deterministic checks and case-evidence retrieval compare confirmed facts, update the EvidenceGraph, surface conflicts immediately, and maintain provisional evidence gaps.

### 7.6 Complete upload set

The officer selects `Hoàn tất tải hồ sơ`. The system freezes an input case version, runs final completeness and conflict checks, and finalizes the intake-gap report. Policy/checklist retrieval runs only when an approved corpus is active.

### 7.7 Prepare handoff

The versioned output contains:

- document inventory and processing status;
- confirmed-fact ledger;
- evidence and provenance map;
- unresolved conflicts;
- formal evidence-gap report;
- draft suggestions for proportionate additional evidence; and
- handoff readiness and stale-item status.

The handoff state is `READY_FOR_SPECIALIST_REVIEW`. It is not a credit decision or recommendation. Any customer-facing document request requires separate human approval.

## 8. Domain contracts

Core records are:

- `CreditCase` and versioned `FinancingRequest`;
- `UploadIntent` binding an expiring object key, case, assigned officer, accepted type, and size ceiling;
- `Document` and immutable `DocumentVersion`;
- `PageRegion` with page and bounding coordinates;
- `CandidateFact` from a deterministic tool or model execution;
- `FactConfirmation` with disposition and actor;
- `ConfirmedFact` created only from an authorized confirmation;
- `Conflict` connecting incompatible facts and sources;
- `EvidenceGap` with provisional/formal state, affected work, and suggested evidence;
- `RetrievalHit` with query and ranked source metadata;
- `AgentExecution` with role, versions, model, inputs, outputs, latency, and validation;
- `Task` and `TaskDependency` for bounded work;
- `HandoffArtifact` bound to a case version; and
- append-only `AuditEvent`.

### 8.1 Required invariants

- An unconfirmed candidate never becomes an authoritative fact.
- A material fact has at least one addressable evidence location.
- A correction never overwrites its source candidate.
- Every gap records evidence considered, missing information, and affected work.
- A changed document creates a version and marks dependent facts, conflicts, gaps, retrieval indexes, and handoffs stale.
- Duplicate content is not silently reprocessed.
- Every state transition records actor, authority, input case version, and time.
- Retrieval output is not a confirmed fact or policy disposition.
- Agent execution cannot expand permissions.
- Chat history cannot become authoritative case state.

## 9. Vietnamese interface

### 9.1 Main screens

- `Danh sách hồ sơ`: assignments, states, unresolved gaps, stale outputs, and activity.
- `Tạo hồ sơ`: financing need and assigned intake officer.
- `Tiếp nhận tài liệu`: uploads, validation, duplicates, progress, and inventory.
- `Xác nhận tài liệu`: split source/candidate review with region highlighting and required dispositions.
- `Đối chiếu hồ sơ`: confirmed facts, conflicts, sources, and affected documents.
- `Khoảng trống bằng chứng`: progressive provisional gaps and the formal finalized report.
- `Bàn giao thẩm định`: versioned fact ledger, evidence map, open issues, and handoff state.
- `Nhật ký kiểm toán`: executions, retrievals, tool calls, human changes, errors, and transitions.

### 9.2 Interaction rules

- Status is always visible at case and document level.
- Confidence never replaces source inspection or human confirmation.
- Missing, conflicting, unreadable, and stale evidence use distinct labels.
- AI-proposed items are visibly labelled as suggestions.
- There are no hidden autonomous state changes.
- The synthetic-data notice remains visible under the current project boundary.

## 10. Security and failure handling

### 10.1 Security

- Authenticated, case-scoped role-based access.
- Assigned-officer enforcement for fact confirmation and correction.
- Encryption in transit and at rest.
- Backend-only secrets and model credentials.
- Short-lived, case-scoped upload authorization and post-upload object verification.
- Separate service identities for Vercel, Cloud Run, Supabase, and FPT.
- Immutable originals separated from derived artifacts.
- File validation, malware scanning, resource limits, and content hashing.
- Case-, version-, permission-, and effective-date-filtered retrieval.
- Data minimization in logs and model telemetry.
- Uploaded documents and retrieved text cannot override trusted instructions or authorize tools.

Retention and deletion controls are configurable but cannot be declared compliant until official requirements are supplied.

### 10.2 Failure behavior

- OCR failure marks pages unreadable and creates manual-review work.
- Schema-invalid model output is rejected and receives bounded retries.
- Unsupported candidates or candidates without source locations are rejected.
- FPT endpoint failure visibly pauses work without a silent external fallback.
- Queue delivery may repeat; jobs are idempotent, leased, checkpointed, and resumable.
- A worker crash leaves recoverable work after lease expiry.
- A stale task cannot write to a newer case or document version.
- Retry exhaustion creates a visible manual-review state.
- Partial processing never produces confirmed facts.
- Retrieval failure produces abstention.
- Every error, retry, override, and recovery creates an audit event.

## 11. Model strategy

The Intake role uses task-appropriate FPT managed endpoints through the backend gateway. Main reasoning begins with Qwen3-30B-A3B only if FPT confirms an instruction/chat endpoint with suitable structured-output behavior. SaoLa3.1-medium 32B is the Vietnamese challenger, and DeepSeek-V4-Flash remains a challenger only if a suitable FPT endpoint exists. Document processing benchmarks FPT.AI-KIE-v1.7 and FPT.AI-Table-Parsing-v1.1, with Qwen2.5-VL-7B-Instruct reserved for complex visual cases. Embedding evaluation compares FPT.AI-e5-large and Vietnamese_Embedding. bge-reranker-v2-m3 is optional rather than a default dependency.

These names define the candidate set, not a production selection. Endpoint capability, data controls, Vietnamese banking quality, schema reliability, evidence grounding, latency, availability, and cost determine the recorded winner. Specialization comes from versioned instructions, scoped context, authorized tools, structured schemas, retrieval, and validation.

There is no initial fine-tuning. Fine-tuning may be proposed later only when:

1. a narrow task has stable ground truth;
2. baseline failures repeat across a sufficiently large reviewed evaluation set;
3. OCR, prompting, schemas, retrieval, and deterministic validation have been improved first;
4. an objective before/after evaluation exists; and
5. licensing, privacy, and deployment constraints are satisfied.

Policies and current rules remain external, versioned, retrievable, and auditable.

## 12. Testing and acceptance

### 12.1 Test layers

1. Deterministic unit tests cover validation, hashing, duplicates, permissions, state transitions, versions, invalidation, and audit.
2. Document-family contract tests cover each Vietnamese document category separately.
3. Model evaluations measure classification, extraction, location grounding, schemas, unsupported candidates, conflicts, gaps, Vietnamese quality, latency, and reliability.
4. Human-control tests verify confirmation authority, correction history, invalidation, and communication gates.
5. Adversarial tests cover prompt injection, unreadable and rotated scans, duplicates, conflicts, missing pages, corrupt files, and resource limits.
6. A blind end-to-end evaluation uses a previously unseen, fully invented Vietnamese case pack uploaded through the normal interface.
7. A generic single-agent chatbot baseline processes the same held-out case for comparison.
8. Infrastructure contract tests cover signed uploads, post-upload verification, queue redelivery, lease expiry, idempotent resume, stale-version rejection, provider timeout, bounded retry, backup restore, and FPT fail-closed behavior.

### 12.2 Comparison dimensions

- document classification accuracy;
- field precision and recall;
- page and source-region accuracy;
- schema-valid output rate;
- unsupported-fact rate;
- conflict and evidence-gap recall;
- correction burden and completion time;
- human-gate compliance;
- audit completeness;
- model latency and availability; and
- total model calls and resource use per case.

### 12.3 Non-negotiable acceptance gates

- Zero unauthorized confirmations.
- Zero unconfirmed candidates in authoritative fact state.
- Zero confirmed material facts without addressable provenance.
- Complete audit coverage for material state changes.
- No silent model fallback.
- No document instruction can change authority or workflow state.

Numerical quality and performance thresholds are recorded only after a representative benchmark establishes realistic baselines; lack of a threshold does not weaken the non-negotiable gates above.

## 13. Product evolution

The product retains all six logical roles and adds them one at a time:

1. Shared Digital Twin, EvidenceGraph, retrieval, audit, and Relationship and Intake Agent.
2. Credit Underwriting Agent with deterministic calculations.
3. Legal, Compliance and Collateral Agent with policy retrieval and controlled checks.
4. Case Orchestrator coordinating the validated specialist contracts.
5. Independent Risk Review Agent enforcing maker-checker challenge.
6. Credit Operations Agent assembling the package and preparing controlled actions.
7. Full-system evaluation and single-agent baseline comparison.

The orchestrator receives a basic deterministic workflow foundation in the first release, but adaptive planner-executor behavior is enabled only after multiple specialist contracts have been independently validated.

## 14. Challenge alignment and product improvements

This design improves alignment with the Digital Expert Agents topic by:

- making the EvidenceGraph, rather than chat, the visible product differentiator;
- demonstrating practical work through controlled case-state changes and handoffs;
- exposing agent traces, tasks, retrievals, tool calls, human gates, and failures;
- preserving distinct specialist duties, permissions, tools, and output contracts;
- proving planner-executor coordination only after specialist quality is measurable;
- comparing against a generic single-agent chatbot on the same held-out case; and
- retaining human authority for credit decisions, exceptions, communications, and operational actions.

## 15. Implementation boundary for the next phase

The next implementation plan covers only the shared foundation and Relationship and Intake Agent described here. It may create interfaces required by later roles, but it must not implement underwriting, legal conclusions, risk challenge, operations, or autonomous credit actions.

The existing implementation plan predates the approved managed architecture and must be revised after this specification is reviewed. The revision must remove local object-storage and direct synchronous processing assumptions; add Supabase signed uploads, Queues, checkpoints, pgvector, and restore controls; add Cloud Run API and worker deployment boundaries; and retain provider-neutral FPT adapters and all human-control invariants.

## 16. Source documents

- `AGENTS.md`
- `docs/PROJECT_CONTEXT.md`
- `docs/BANKING_WORKFLOW.md`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/EVIDENCE_GAP_RESOLUTION.md`
- `docs/DOMAIN_MODEL.md`
- `docs/TECHNICAL_DIRECTION.md`
- `docs/PRODUCT_BOUNDARIES.md`
- `docs/OPEN_QUESTIONS.md`
- `docs/DECISION_LOG.md`
- `/Users/an/Downloads/PROBLEM STATEMENT - SHB2.pdf`
