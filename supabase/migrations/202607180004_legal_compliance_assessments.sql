-- PROPOSED reviewer output store for the Legal, Compliance and Collateral
-- Agent.  Assessments are append-only potential-issue analysis, never a
-- legal determination: the payload schema has no wrongdoing/waiver/
-- collateral-value field and every finding carries citations (enforced by
-- the application schema; provenance columns are extracted here for audit
-- queries).  All data is synthetic.
--
-- Also introduces the policy-corpus-version registry (ADR-0002) and the
-- append-only controlled-check record store (KYC/AML-watchlist/related-party
-- — mock only, never a production compliance check).  The READY_FOR_RISK_
-- REVIEW handoff state this agent uses was already added additively by
-- 202607180003 for the underwriting maker; both specialists feed the same
-- checker state and no further handoff constraint change is required here.

create table public.legal_compliance_assessments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.credit_cases(id) on delete restrict,
  case_version integer not null check (case_version > 0),
  task_id uuid not null,
  execution_id uuid not null,
  agent_role text not null default 'LEGAL_COMPLIANCE_COLLATERAL'
    check (agent_role = 'LEGAL_COMPLIANCE_COLLATERAL'),
  prompt_version text not null check (length(btrim(prompt_version)) > 0),
  model_id text not null check (length(btrim(model_id)) > 0),
  endpoint_id text not null check (length(btrim(endpoint_id)) > 0),
  assessment jsonb not null check (jsonb_typeof(assessment) = 'object'),
  assessment_schema_version text not null default 'legal-assessment-v1'
    check (length(btrim(assessment_schema_version)) > 0),
  evidence_view_built_at timestamptz not null,
  created_at timestamptz not null default clock_timestamp(),
  -- Composite case FK through the source task: the assessment binds to the
  -- exact task row (and therefore case + case version) that produced it.
  constraint legal_compliance_assessments_task_case_fk
    foreign key (task_id, case_id, case_version)
    references public.processing_tasks(id, case_id, case_version)
    on delete restrict,
  -- One durable reviewer output per (case, version, task): duplicate
  -- delivery resolves to the existing row instead of a second assessment.
  constraint legal_compliance_assessments_task_key
    unique (case_id, case_version, task_id),
  constraint legal_compliance_assessments_time_order
    check (evidence_view_built_at <= created_at)
);

create index legal_compliance_assessments_case_idx
  on public.legal_compliance_assessments (case_id, case_version, created_at desc);

create trigger legal_compliance_assessments_are_append_only
before update or delete on public.legal_compliance_assessments
for each row execute function public.reject_append_only_mutation();

alter table public.legal_compliance_assessments enable row level security;
alter table public.legal_compliance_assessments force row level security;

create policy legal_compliance_assessments_select_assigned
on public.legal_compliance_assessments
for select to authenticated using (
  exists (
    select 1 from public.case_assignments as assignment
    where assignment.case_id = legal_compliance_assessments.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

revoke all on public.legal_compliance_assessments from public, anon, authenticated;

grant select on public.legal_compliance_assessments to authenticated;

grant all on public.legal_compliance_assessments to service_role;

-- Policy corpus version registry (ADR-0002): which synthetic, checksum-
-- verified corpus version(s) have been loaded and used.  Never described as
-- an official SHB policy source; the label column makes that explicit for
-- every registered row, including any future official corpus that may
-- eventually replace it (only the configuration changes, per ADR-0002).
create table public.policy_corpus_versions (
  corpus_id text not null check (length(btrim(corpus_id)) > 0),
  version text not null check (length(btrim(version)) > 0),
  checksum_sha256 text not null check (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  loaded_at timestamptz not null default clock_timestamp(),
  active boolean not null default true,
  is_synthetic boolean not null default true,
  primary key (corpus_id, version)
);

alter table public.policy_corpus_versions enable row level security;
alter table public.policy_corpus_versions force row level security;

-- The corpus registry names no case; every case participant may read which
-- corpus versions are in use, but only the backend service role may write.
create policy policy_corpus_versions_select_authenticated
on public.policy_corpus_versions
for select to authenticated using (true);

revoke all on public.policy_corpus_versions from public, anon, authenticated;

grant select on public.policy_corpus_versions to authenticated;

grant all on public.policy_corpus_versions to service_role;

-- Controlled-check records (KYC / AML+watchlist / related-party): append-
-- only, mock-only.  ``is_mock`` defaults true and every adapter this project
-- ships always sets it; a future production adapter cannot silently claim
-- mock provenance.
create table public.controlled_check_records (
  id uuid primary key,
  case_id uuid not null references public.credit_cases(id) on delete restrict,
  case_version integer not null check (case_version > 0),
  task_id uuid not null,
  check_type text not null
    check (check_type in ('KYC', 'AML_WATCHLIST', 'RELATED_PARTY')),
  provider_id text not null check (length(btrim(provider_id)) > 0),
  tool_name text not null check (length(btrim(tool_name)) > 0),
  tool_version text not null check (length(btrim(tool_version)) > 0),
  subject_type text not null check (subject_type in ('ENTITY', 'INDIVIDUAL')),
  subject_ref_vi text not null check (length(btrim(subject_ref_vi)) > 0),
  status text not null check (status in ('CLEAR', 'HIT', 'INCONCLUSIVE')),
  result_summary_vi text not null check (length(btrim(result_summary_vi)) > 0),
  result_payload jsonb not null default '{}'::jsonb
    check (jsonb_typeof(result_payload) = 'object'),
  is_mock boolean not null default true check (is_mock),
  invoked_at timestamptz not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint controlled_check_records_task_case_fk
    foreign key (task_id, case_id, case_version)
    references public.processing_tasks(id, case_id, case_version)
    on delete restrict,
  constraint controlled_check_records_time_order
    check (invoked_at <= created_at)
);

create index controlled_check_records_case_idx
  on public.controlled_check_records (case_id, case_version, task_id);

create trigger controlled_check_records_are_append_only
before update or delete on public.controlled_check_records
for each row execute function public.reject_append_only_mutation();

alter table public.controlled_check_records enable row level security;
alter table public.controlled_check_records force row level security;

create policy controlled_check_records_select_assigned
on public.controlled_check_records
for select to authenticated using (
  exists (
    select 1 from public.case_assignments as assignment
    where assignment.case_id = controlled_check_records.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

revoke all on public.controlled_check_records from public, anon, authenticated;

grant select on public.controlled_check_records to authenticated;

grant all on public.controlled_check_records to service_role;
