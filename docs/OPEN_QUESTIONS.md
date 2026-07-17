# Open Questions

## Status

**OPEN QUESTION:** The questions below are unresolved and must not be silently converted into requirements or banking rules. Official SHB or project-team sources should answer material business and policy questions before implementation.

When sources conflict:

1. preserve both interpretations and their provenance;
2. describe the practical impact of the conflict;
3. record it in this document;
4. avoid implementing the affected material banking rule; and
5. obtain clarification from an authorized source.

No source conflicts have been identified in the current repository because no official SHB policy, checklist, workflow configuration, or API documentation has been supplied.

## Business and banking

- What is SHB's official SME working-capital document checklist?
- Which human roles are responsible for underwriting, independent risk review, legal review, collateral review, operations, and approval?
- Which conditions are blocking before human credit consideration or approval?
- Which conditions may remain outstanding until signing or disbursement?
- How are policy exceptions identified, escalated, decided, and recorded?
- What credit proposal or credit memo format and mandatory sections does SHB use?
- Which workflow steps are handled by LOS, ACAS, or other systems?
- What are the official Vietnamese and English names for relevant roles, stages, case states, and artifacts?
- What delegation-of-authority rules apply to customer communication, exception disposition, and operational actions?
- Is a legal or collateral checker required independently from the combined conceptual specialist role?

## Policy and evidence

- Which official policy corpus, versions, effective dates, and access controls will be available?
- Which requirements are deterministic rules, and which require professional judgment?
- What source hierarchy applies when policies, procedures, checklists, or templates conflict?
- What materiality thresholds determine whether a gap is BLOCKING, CONDITIONAL, or CLARIFICATION?
- Who may close or downgrade an evidence gap, and what evidence must support that action?
- What document validity, expiry, certification, translation, and copy-quality rules apply?
- Which data fields are necessary and permitted for each stage of the case?

## Workflow and integration

- What are the official case states, allowed transitions, service-level expectations, and escalation paths?
- Which new documents invalidate which analyses or memo sections?
- What human approval artifact is required before a proposed action may execute?
- Which mock interfaces are needed for the demonstrator?
- If later integration is considered, which systems are systems of record and which actions are read-only versus state-changing?
- What audit, retention, access-review, and data-deletion requirements apply?

## Technical and infrastructure

- Which Supabase and Google Cloud regions are permitted for the intended data class, and do they satisfy the required SHB and Vietnamese data-residency controls?
- Which cross-border transfers occur between Vercel, Supabase, Cloud Run, and FPT endpoints, including prompts, extracted text, embeddings, logs, and telemetry?
- What private connectivity, egress allow-listing, mTLS, IP restriction, and service-identity options are available for each provider?
- Which Supabase backup, point-in-time recovery, object-versioning, object-backup, restore-testing, retention, and deletion controls are required? Database backup must not be assumed to back up Storage objects.
- What recovery-point and recovery-time objectives apply to case state, queue messages, documents, derived artifacts, and audit events?
- What Cloud Run region, minimum instances, concurrency, CPU, memory, request timeout, worker schedule, and maximum task duration are required?
- What identity provider and workforce SSO integration will be used, and how will assigned-officer claims be mapped and reviewed?
- What secrets manager, key-management, log-redaction, malware-scanning, DLP, and security-monitoring services are approved?
- Which exact FPT managed endpoint identifiers, context limits, structured-output capabilities, quotas, rate limits, latency commitments, telemetry controls, and data-retention terms are available?
- Is a private or dedicated FPT endpoint required for the intended data class?
- Which model best satisfies Vietnamese banking and tool-calling benchmarks?
- Does FPT provide a chat/instruction-tuned Qwen3-30B-A3B endpoint suitable for the main reasoning candidate?
- Should SaoLa3.1-medium 32B and DeepSeek-V4-Flash be retained as challengers based on endpoint availability and benchmark results?
- Do FPT.AI-KIE-v1.7, FPT.AI-Table-Parsing-v1.1, Qwen2.5-VL-7B-Instruct, FPT.AI-e5-large, Vietnamese_Embedding, and bge-reranker-v2-m3 meet the required document and retrieval benchmarks?
- Is a hosted-model fallback permitted?
- What document types, languages, image quality, file sizes, and volumes must be supported first?
- What level of Vietnamese-language extraction, retrieval, reasoning, and drafting performance is required?
- What end-to-end concurrency, latency, availability, and cost-per-document targets must the managed architecture meet?

## Evaluation

- What metrics will judges prioritize?
- Do competition rules permit the confirmed FPT AI Factory target, or do they require another infrastructure provider?
- How should the multi-agent system be compared with a single-agent baseline?
- Is the expected demonstration limited to pre-approval preparation and review, or extended to mock post-approval operations?
- Which synthetic case scenarios and ground-truth annotations will be used?
- What thresholds apply to citation accuracy, gap detection, calculation correctness, task completion, latency, and human-gate enforcement?
- How should abstention, uncertainty calibration, contradictory evidence, and manual escalation be scored?
- What evidence is required to demonstrate separation of duties and auditability?

## Assumptions pending confirmation

These assumptions support documentation only and are not official SHB requirements:

- **ASSUMPTION:** Conceptual human functions include intake, underwriting, legal/compliance/collateral, independent risk, operations, and authorized approval.
- **ASSUMPTION:** The illustrative customer-document groups are sufficient for designing synthetic cases but are not a checklist.
- **ASSUMPTION:** The first demonstrator will use synthetic policy content and mock system responses.
- **ASSUMPTION:** The combined Legal, Compliance and Collateral Agent is a useful initial logical role; official separation may differ.
- **ASSUMPTION:** Approval records can bind to a versioned case or artifact in a future design.

## Resolution record format

When a question is answered, move the confirmed outcome to [Decision Log](DECISION_LOG.md) with:

- the authoritative source and date;
- the decision and rationale;
- alternatives considered;
- status and effective scope; and
- conditions that would invalidate or require review of the decision.

Retain a short pointer here if the history is useful.

## Related documents

- [Project Context](PROJECT_CONTEXT.md)
- [Banking Workflow](BANKING_WORKFLOW.md)
- [Technical Direction](TECHNICAL_DIRECTION.md)
- [Decision Log](DECISION_LOG.md)
