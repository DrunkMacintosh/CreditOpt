# SHB CreditOps EvidenceGraph — Hackathon Pitch Deck Design

**Project:** SHB CreditOps EvidenceGraph
**Design status:** Approved in conversation on 2026-07-17
**Implementation status:** Deck not yet built
**Deliverable:** One PowerPoint file (.pptx), 16:9, Vietnamese
**Occasion:** Hack CX Together 2026 — SHB challenge "Digital Expert Agents – A Team of AI Specialists for Banking Operations"; 15+ minute slot including a live demo segment

## 1. Purpose

This specification defines the content, narrative, and per-slide copy for the hackathon pitch deck. It adapts a proven 18-slide "winning pitch" rhetorical arc (hook → problem → product → proof → win) — originally drafted around a retail product-advisor concept — to the actual project in this repository. The deck presents the project as a built solution, supported by a live demonstration.

The deck's source of truth for all product claims is the repository documentation ([Project Context](../../PROJECT_CONTEXT.md), [Agent Architecture](../../AGENT_ARCHITECTURE.md), [Banking Workflow](../../BANKING_WORKFLOW.md), [Evidence Gap Resolution](../../EVIDENCE_GAP_RESOLUTION.md), [Domain Model](../../DOMAIN_MODEL.md), [Technical Direction](../../TECHNICAL_DIRECTION.md), [Product Boundaries](../../PRODUCT_BOUNDARIES.md)) and the official problem statement (`tmp/pdfs/problem-statement-shb2.txt`).

## 2. Decisions confirmed during brainstorming

| Decision | Choice |
|---|---|
| Deck subject | SHB CreditOps EvidenceGraph (this repository's project, not the retail-advisor concept the skeleton came from) |
| Demo reality | **ASSUMPTION (team plan):** a working demo will exist by pitch day — intake vertical slice, 2–3+ collaborating specialist agents, and the trace dashboard, on synthetic data. If the build slips, slides 6 and 13 must be reframed before presenting (see §6). |
| Language | Vietnamese slide copy; established technical terms kept in English with a Vietnamese gloss on first use (EvidenceGraph, Credit Case Digital Twin, maker–checker, planner–executor, RAG, agent) |
| Length | Full 18-slide arc; the 15+ minute slot also contains a separate live-demo segment |
| Product name | "SHB CreditOps EvidenceGraph" — full confirmed name used everywhere |
| Narrative spine | "A digital credit department" frame; verifiable evidence as the differentiation thread (slides 7–11); one synthetic SME case as the running example |
| Final deliverable | .pptx built from this spec (implementation planned separately) |

## 3. Design foundations

### 3.1 Narrative frame

The deck argues: *SHB asked for a team of AI specialists; we built the first digital credit department **for** SHB* — six bounded roles mirroring a real credit unit, coordinated by an orchestrator, pausing at human gates. Phrasing is always "cho SHB" (for SHB) / "đề xuất cho SHB" (proposed to SHB) — never wording that implies SHB endorsement, ownership, or approval, which the [claims boundary](../../PRODUCT_BOUNDARIES.md) prohibits.

### 3.2 Running example case

*Công ty TNHH Thực phẩm Minh An* — a fully synthetic food-processing SME:

- Need: **2 tỷ VND** working capital to purchase raw materials for Tet-season orders
- Repayment source: customer collections
- Document set: ~20 synthetic documents — enterprise registration, charter, legal-representative ID, two years of financial statements, bank statements, VAT declarations, supplier purchase contracts, customer sales contracts, inventory plan, collateral papers
- Planted test issues for the demo: a revenue figure that does not reconcile with bank statements (conflict → gap), and repayment concentration on one buyer (risk-review challenge)

This case appears on slides 1, 5, 6, 8, and 18 and is the live-demo scenario.

### 3.3 Claims discipline

- Demo capabilities are described as "đã xây dựng" (built) only if they run in the demo; roadmap items are "kế hoạch" (planned).
- The deck must not claim production readiness, regulatory compliance, security certification, official SHB policy status for synthetic content, or SHB approval/endorsement.
- Every slide showing case data, screenshots, or policies carries the mandatory disclaimer (canonical English sentence, shown in Vietnamese with the English original in the footer):
  - VN: *"Toàn bộ dữ liệu khách hàng, chính sách, tài liệu và phản hồi hệ thống ngân hàng trong dự án là dữ liệu tổng hợp, được tạo riêng cho mục đích trình diễn."*
  - EN (canonical): *"All customer data, policies, documents, and banking-system responses in this project are synthetic and created solely for demonstration."*
- Validation numbers (slide 13) and impact numbers (slide 15) ship only as measured values from real runs; the bracketed slots in this spec are deliberate data slots, not optional decoration. The deck must not be presented with brackets remaining.

### 3.4 Visual identity

SHB-inspired palette (SHB orange + deep blue; exact codes confirmed from public SHB brand references during the pptx build), generous whitespace, one dominant visual per slide, dashboard screenshots with annotation callouts. Footer on every slide: product name + slide number + disclaimer where required by §3.3.

## 4. Slide-by-slide specification

Reading convention: quoted Vietnamese **titles** and **killer lines** are final on-slide copy. Body bullets are content specifications — during the pptx build they are rendered as concise Vietnamese on-slide text following the §2 language rule, and any longer explanations move to speaker notes.

### Slide 1 — Hook

- **Title:** "Một câu hỏi đơn giản. Hàng chục tài liệu. Năm bàn làm việc."
- **Core message:** The Minh An director asks: *"Tôi cần 2 tỷ nhập nguyên liệu cho đơn hàng Tết — ngân hàng cần gì để cho tôi vay?"* Behind that one sentence: a wall of scans, spreadsheets, and contracts that five specialists must read, cross-check, and challenge before anyone can answer.
- **Visual:** Left — a single chat-bubble question from the director. Right — a chaotic pile of 20+ document thumbnails.
- **Purpose:** Judges feel that SME credit is slow not at the *decision* but at the *preparation*.

### Slide 2 — The problem is not lack of data

- **Title:** "Ngân hàng không thiếu dữ liệu. Ngân hàng thiếu bộ máy kiểm chứng dữ liệu."
- **Content blocks:** Tài liệu — có. Chính sách — có. Chuyên gia — có. Nhưng: completeness checked by hand → conflicts (revenue vs bank statements) discovered late → policy citations found manually → memo assembled by copy-paste → audit trail reconstructed after the fact.
- **Killer line:** *"Khoảng trống không nằm ở thông tin — mà ở việc kiểm chứng và kết nối thông tin."*

### Slide 3 — Why now

- **Title:** "AI ngân hàng đang dừng ở trả lời câu hỏi. Nghiệp vụ cần AI làm việc."
- **Urgency angles** (sourced from the problem statement's "Why This Problem Matters"): current bank AI = RAG/Q&A chatbots; the 2026 landscape shifts to agentic AI that plans, coordinates, uses tools, and acts; expertise is locked in scarce individual experts; naive agents cannot be trusted with credit — no evidence, no audit trail, no separation of duties.
- **Visual:** Maturity curve *Chatbot Q&A → RAG → Agentic teamwork*, with a red **"khoảng cách tin cậy"** (trust gap) blocking the final step.
- **Killer line:** *"Đúng lúc ngân hàng cần AI làm việc thật, chatbot chỉ có thể nói."*

### Slide 4 — Our product

- **Title:** "SHB CreditOps EvidenceGraph — Phòng tín dụng số đầu tiên cho SHB"
- **One-line pitch:** *"Một đội ngũ chuyên gia AI biến chồng tài liệu rời rạc thành hồ sơ tín dụng có bằng chứng — để con người ra quyết định."*
- **Three promises:**
  1. **Một đội ngũ, không phải một chatbot** — six bounded roles: Điều phối (Case Orchestrator), Tiếp nhận (Relationship & Intake), Thẩm định (Credit Underwriting), Pháp lý–Tuân thủ–TSBĐ (Legal, Compliance & Collateral), Kiểm soát rủi ro độc lập (Independent Risk Review), Vận hành tín dụng (Credit Operations).
  2. **Mọi kết luận đều có bằng chứng** — each material claim traces to a document version, page, deterministic calculation, or exact policy citation (the EvidenceGraph).
  3. **Con người quyết định** — AI prepares, challenges, and drafts; every approval belongs to an authorized officer, enforced by workflow gates.
- **Visual:** The six roles arranged around a central **Credit Case Digital Twin** hub + one clean Vietnamese dashboard screenshot.

### Slide 5 — Before / After

- **Title:** "Từ xử lý thủ công sang hồ sơ được chuẩn bị sẵn"
- **Before:** Documents arrive over email/Zalo → officer sorts and retypes by hand → missing papers discovered weeks in → repeated customer callbacks → underwriter re-reads everything → risk reviewer asks "source?" → memo assembled by copy-paste. Timeline bar: **weeks**.
- **After:** Upload once → agents classify and extract with confidence scores → officer confirms document-by-document → gaps and conflicts surface immediately with suggested follow-ups (human approves any customer request) → underwriting and legal run in parallel on shared case state → independent challenge → draft memo with clickable citations. Timeline bar: **days**.
- **Killer contrast:** *"Trước: con người phục vụ hồ sơ. Sau: hồ sơ được chuẩn bị để con người quyết định."*

### Slide 6 — Demo journey (Minh An case)

- **Title:** "Một hồ sơ hoàn chỉnh, trong một cuộc trình diễn"
- **Six-step storyboard**, each step a real dashboard screenshot:
  1. Officer creates the case and uploads ~20 Minh An documents.
  2. Live agent traces: classification → KIE/table extraction → facts with confidence; officer confirms each document.
  3. **Conflict caught:** financial-statement revenue does not reconcile with bank statements → gap record (mức độ BLOCKING) with suggested evidence and rationale → officer approves the document request.
  4. Underwriting + Legal/Collateral run in parallel; deterministic tools compute ratios and the working-capital need.
  5. **Independent Risk Review challenges** repayment concentration on one buyer → maker responds; the exchange stays visible.
  6. Credit Operations assembles the draft memo — every number clicks through to its source; the final gate waits for the human decision.
- **Footer:** mandatory synthetic-data disclaimer (§3.3).
- **Role in the talk:** 60-second preview; the live demo later runs the same case for real.

### Slide 7 — Behind the interface

- **Title:** "Hệ thống không trò chuyện về hồ sơ. Hệ thống xử lý hồ sơ."
- **Pipeline** (8 steps, drawn as a swimlane across the agent roles):
  1. Tiếp nhận nhu cầu — structure amount / purpose / term / repayment / collateral
  2. Số hoá & phân loại tài liệu — parse, OCR, classify, immutable versions
  3. Trích xuất dữ kiện — facts with source location + confidence
  4. Cán bộ xác nhận từng tài liệu — model output remains a candidate until confirmed
  5. Phát hiện xung đột & khoảng trống — Evidence Gap Resolution (BLOCKING / CONDITIONAL / CLARIFICATION)
  6. Phân tích chuyên môn song song — underwriting + legal/compliance/collateral on shared state
  7. Phản biện độc lập — maker–checker
  8. Tổng hợp tờ trình & gate phê duyệt — draft memo, human decision
- **Killer line:** *"Chat không phải là hồ sơ. Hồ sơ là Credit Case Digital Twin — có phiên bản, có bằng chứng, có kiểm toán."*

### Slide 8 — The engine: EvidenceGraph

- **Title:** "Mọi kết luận đều được truy vết — không phỏng đoán."
- **Provenance chain diagram:** document version → page/region → extracted fact → deterministic calculation / policy citation → finding → independent challenge → human approval. One worked example: the Minh An working-capital figure decomposed into its cited sources.
- **Gap-record anatomy (side panel):** issue, existing evidence, missing information, suggested documents, rationale, policy basis, blocking level, affected tasks, approval status.
- **Why judges care:** findings are *data structures with lineage*, not paragraphs — proof the system is more than an LLM wrapper.

### Slide 9 — Data grounding & trust

- **Title:** "Không có con số bịa. Không có chính sách tưởng tượng. Không có kết luận thiếu nguồn."
- **Grounding sources:** immutable versioned customer documents; officer-confirmed facts; deterministic calculators; versioned policy corpus with exact citations (policy RAG); controlled mock KYC/AML lookups; append-only audit log.
- **Two differentiating trust principles:**
  - **Fail-closed:** no source → the system abstains and routes to manual review; retrieval failure never becomes "no policy applies."
  - **Untrusted documents:** uploaded files are data, never commands — document text cannot alter agent instructions, permissions, or workflow state (prompt-injection defense).
- **Visual:** sources flowing into "Lớp bằng chứng" (Evidence Layer) → agent responses, with a visible abstain branch to manual review.

### Slide 10 — Architecture

- **Title:** "Kiến trúc cho độ chính xác, chủ quyền dữ liệu và khả năng mở rộng"
- **Block diagram:** Vercel (Next.js Vietnamese UI) → Cloud Run (FastAPI API + `creditops-worker` Job; deterministic state machine; provider-neutral model gateway) → Supabase (Postgres Digital Twin + EvidenceGraph edges, Queues, private Storage, pgvector) → FPT AI Factory managed inference (candidates: Qwen3-30B-A3B reasoning, SaoLa3.1-medium 32B Vietnamese challenger, FPT.AI-KIE-v1.7, FPT.AI-Table-Parsing-v1.1, Qwen2.5-VL-7B fallback, FPT.AI-e5-large / Vietnamese_Embedding). Model names presented as the benchmark-gated candidate stack, consistent with [Technical Direction](../../TECHNICAL_DIRECTION.md).
- **Trust boundaries highlighted:** the frontend never calls models; models never own state; every model output passes schema validation before touching the case.
- **Technical points:** two RAG paths (case evidence + policy); durable queues with checkpoints and idempotent retries; human-gate state machine; append-only audit; Vietnamese-first benchmark-gated model selection; inference on FPT's Southeast Asia infrastructure (data-control story for a bank).
- **Killer line:** *"Mô hình có thể thay. Kiến trúc ra quyết định thì không."*

### Slide 11 — Differentiation

- **Title:** "Chatbot tìm câu trả lời. Chúng tôi chuẩn bị quyết định."
- **Comparison table** — columns: Quy trình thủ công | Chatbot RAG đơn | Multi-agent demo thông thường | SHB CreditOps EvidenceGraph. Rows:
  - Đọc & trích xuất tài liệu tiếng Việt thật (KIE, bảng biểu)
  - Phát hiện thiếu sót & mâu thuẫn giữa các tài liệu
  - Truy vết bằng chứng cho từng kết luận
  - Phân tách maker–checker (thẩm định ≠ phản biện)
  - Gate phê duyệt của con người trong workflow
  - Dashboard truy vết agent & kiểm toán
  - Chống chỉ thị ẩn trong tài liệu (prompt injection)
- **Positioning note:** the third column concedes other teams will also show multi-agent demos, then beats them on verifiability, separation of duties, and audit — "designed for banking, not for demo day."

### Slide 12 — Built to the judging criteria

- **Title:** "Đề bài yêu cầu — chúng tôi xây đúng, rồi đi xa hơn một tầng tin cậy."
- **Checklist table** mapping official problem-statement deliverables → what the demo shows:
  - ≥2–3 specialist digital experts (Credit, Legal/Compliance, Operations) → six bounded roles, including exactly those three
  - Planner–executor orchestration → Case Orchestrator decomposes and routes; bounded executors
  - Practical tool use (APIs, data, concrete actions) → KIE/table extraction, deterministic calculators, controlled mock lookups, memo generation
  - Domain-specific RAG per agent → case-evidence RAG + policy RAG with exact citations
  - Dashboard of agent traces, task status, decisions, collaboration flows → the trace/audit UI
  - Single-agent chatbot comparison → measured head-to-head (slide 13)
- **Bottom band** — the brief's "Benefits to the Bank," echoed back: GenAI from answering → working; one coordinated system representing multiple departments; less dependence on scarce individual experts *while preserving controls*; foundation for end-to-end process automation.

### Slide 13 — Validation

- **Title:** "Chúng tôi không chỉ demo. Chúng tôi đo."
- **Test design:** [N] synthetic SME cases across six scenario types (complete / missing-document / conflicting-data / policy-exception / poor-scan / manual-review) with ground-truth annotations; head-to-head against a single-agent RAG chatbot using the *same base model* — isolating the value of orchestration + evidence discipline.
- **Metric panel** (measured-value slots; see §3.3):
  - Citation coverage: % of material conclusions with a correct source — [X%] vs chatbot [Y%]
  - Gap detection recall/precision on planted issues — [X%]
  - Calculation correctness via deterministic tools — target 100%
  - Unsupported-claim rate — [X%] vs chatbot [Y%]
  - Human-gate enforcement — 0 bypasses across all runs
  - End-to-end preparation time vs manual baseline — [X hours → Y minutes]
- **Killer line:** *"Câu hỏi không phải là demo có đẹp không — mà là hệ thống có đáng tin để đứng cạnh một quyết định tín dụng không."*

### Slide 14 — Scalability

- **Title:** "Nghiệp vụ mới — cùng một bộ máy bằng chứng."
- **Core argument:** nothing in the engine is hard-coded to working-capital loans; expansion = new document schemas, policy corpora, role instructions, and tools — not a new architecture. The provider-neutral gateway means model upgrades never rebuild the app.
- **Three expansion axes** (all labeled planned):
  1. Deeper in the lifecycle: stages 7–14 — notification, contracts, security completion, disbursement-condition checks, then the future Monitoring & Recovery Agent.
  2. More credit products: term loans, guarantees, trade finance/LC, retail lending.
  3. Other banking operations: KYC review, internal audit preparation, claims processing — same pattern (evidence twin + bounded specialists + human gates).

### Slide 15 — Business impact

- **Title:** "Hồ sơ tốt hơn → quyết định nhanh hơn → vốn đến doanh nghiệp sớm hơn."
- **Impact areas:** SME time-to-decision from weeks toward days; fewer document round-trips (gaps caught at intake, one consolidated request); consistent policy application across branches; less dependence on scarce senior experts; audit trail generated during work rather than reconstructed after; higher officer throughput per headcount.
- **Metric slots** (measured or clearly sourced only): giảm [X%] thời gian chuẩn bị hồ sơ; giảm [X] vòng bổ sung tài liệu; tăng [X%] công suất mỗi cán bộ.
- **Strategic frame:** SME lending is a growth priority; the bottleneck is preparation capacity — this system is that capacity.

### Slide 16 — Roadmap

- **Now (hackathon):** working demo — intake slice + collaborating specialists + trace dashboard, synthetic data, on the real target architecture (Vercel / Cloud Run / Supabase / FPT AI Factory).
- **+1 month:** lock model endpoints via Vietnamese banking benchmarks; harden extraction across all document families; complete six-role coverage.
- **+3 months:** shadow-mode pilot with an SHB credit team using the official checklist and policy corpus *(requires SHB data and governance approval — stated on-slide)*.
- **+6 months:** controlled LOS/ACAS integration boundaries; extend to post-approval preparation stages.
- **Future:** monitoring agent, omnichannel intake, multimodal documents.
- **Honesty note on-slide:** post-hackathon phases proceed under SHB governance, security acceptance, and data-residency approvals.

### Slide 17 — Team

- **Title:** "Đội ngũ xây AI đáng tin cho ngân hàng"
- **Per member (data slots to fill):** name / role / what they built in the demo / relevant strength. Suggested role split: AI-LLM engineer, backend-data engineer, product & design, banking-domain lead, evaluation lead.
- **Killer line:** *"Chúng tôi kết hợp kỹ thuật AI, tư duy sản phẩm và hiểu biết nghiệp vụ tín dụng."*

### Slide 18 — Closing / Ask

- **Title:** "Biến chồng tài liệu rời rạc thành quyết định tín dụng có bằng chứng."
- **CTA block:** QR code → live demo with the Minh An case; invite judges to hand the system a fresh synthetic case; ask for pilot support with a real SHB credit team.
- **Final line:** *"Không phải thêm một chatbot — mà là một đội ngũ chuyên gia số có thể kiểm chứng, cho nghiệp vụ cốt lõi nhất của ngân hàng."*

## 5. Compliance checklist for the built deck

- [ ] Disclaimer present on every slide showing case data, screenshots, or policy content (§3.3)
- [ ] No bracketed metric slots remain; every number traces to a measured run or a cited source
- [ ] No wording implying SHB approval, endorsement, ownership, production readiness, or regulatory compliance
- [ ] Built vs planned labeling consistent with what the demo actually runs on pitch day
- [ ] Model names presented as benchmark-gated candidates, not final selections

## 6. Inputs required before the pptx is final

| Input | Owner | Blocking for |
|---|---|---|
| Team member names, roles, contributions | Team | Slide 17 |
| Measured validation numbers from demo runs | Evaluation lead | Slides 13, 15 |
| Dashboard screenshots (Vietnamese UI, Minh An case) | Team | Slides 4, 6, 8 |
| QR link to demo | Team | Slide 18 |
| Exact SHB brand color codes | Designer | All slides |
| Hackathon submission constraints (template, file naming, deadline) | Team | Packaging |
| Demo status confirmation near pitch day | Team | §2 demo assumption; reframe slides 6/13 if the build slips |

## 7. Out of scope

- Building the .pptx itself (next step: implementation plan)
- Implementing the demo system (covered by the separate [intake-agent plan](../plans/2026-07-17-relationship-intake-agent-implementation.md))
- An English or bilingual deck variant
- Speaker script / talk-track beyond the on-slide copy (may be added during implementation planning)

## 8. Next step

Produce the implementation plan for building the .pptx from this specification (slide masters, diagram production order, screenshot capture list, review passes).
