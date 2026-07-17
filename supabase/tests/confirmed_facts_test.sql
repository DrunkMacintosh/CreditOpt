begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_catalog;

select plan(18);

insert into public.credit_cases (id, case_version, workflow_state, created_by)
values (
  '10000000-0000-0000-0000-000000000001', 1, 'INTAKE_DRAFT',
  '00000000-0000-0000-0000-000000000001'
);

insert into public.case_assignments (case_id, officer_id, assigned_by, assigned_at)
values (
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000010',
  clock_timestamp() - interval '10 seconds'
);

insert into public.documents (id, case_id, created_by)
values (
  '60000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001'
);

insert into public.document_versions (
  id, document_id, case_id, case_version, version,
  storage_bucket, storage_object_key, original_filename,
  declared_content_type, byte_size, content_sha256, created_by
)
values (
  '61000000-0000-0000-0000-000000000001',
  '60000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001', 1, 1,
  'creditops-originals', 'originals/61000000-0000-0000-0000-000000000001',
  'synthetic.pdf', 'application/pdf', 1024, repeat('b', 64),
  '00000000-0000-0000-0000-000000000001'
);

insert into public.page_regions (
  id, case_id, case_version, document_version_id, page_number,
  x, y, width, height, extraction_method
)
values (
  '62000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001', 1,
  '61000000-0000-0000-0000-000000000001', 1,
  0, 0, 0.5, 0.5, 'SYNTHETIC_TEST'
);

insert into public.candidate_facts (
  id, case_id, case_version, document_version_id, page_region_id,
  field_key, proposed_value, confidence, extraction_method
)
values
  (
    '63000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001', 1,
    '61000000-0000-0000-0000-000000000001',
    '62000000-0000-0000-0000-000000000001',
    'synthetic.amount', '100'::jsonb, 0.9, 'SYNTHETIC_TEST'
  ),
  (
    '63000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001', 1,
    '61000000-0000-0000-0000-000000000001',
    '62000000-0000-0000-0000-000000000001',
    'synthetic.corrected', '200'::jsonb, 0.8, 'SYNTHETIC_TEST'
  ),
  (
    '63000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000001', 1,
    '61000000-0000-0000-0000-000000000001',
    '62000000-0000-0000-0000-000000000001',
    'synthetic.absent', '300'::jsonb, 0.7, 'SYNTHETIC_TEST'
  ),
  (
    '63000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000001', 1,
    '61000000-0000-0000-0000-000000000001',
    '62000000-0000-0000-0000-000000000001',
    'synthetic.unreadable', '400'::jsonb, 0.6, 'SYNTHETIC_TEST'
  ),
  (
    '63000000-0000-0000-0000-000000000005',
    '10000000-0000-0000-0000-000000000001', 1,
    '61000000-0000-0000-0000-000000000001',
    '62000000-0000-0000-0000-000000000001',
    'synthetic.revoked', '500'::jsonb, 0.5, 'SYNTHETIC_TEST'
  );

insert into public.fact_confirmations (
  id, case_id, case_version, candidate_fact_id, disposition,
  corrected_value, actor_id, assigned_officer_id, authority_source,
  authority_granted_at, confirmed_at
)
values
  (
    '64000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001', 1,
    '63000000-0000-0000-0000-000000000001', 'ACCEPTED', null,
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
    clock_timestamp() - interval '2 seconds',
    clock_timestamp() - interval '1 second'
  ),
  (
    '64000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001', 1,
    '63000000-0000-0000-0000-000000000002', 'CORRECTED', '250'::jsonb,
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
    clock_timestamp() - interval '2 seconds',
    clock_timestamp() - interval '1 second'
  ),
  (
    '64000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000001', 1,
    '63000000-0000-0000-0000-000000000003', 'ABSENT', null,
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
    clock_timestamp() - interval '2 seconds',
    clock_timestamp() - interval '1 second'
  ),
  (
    '64000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000001', 1,
    '63000000-0000-0000-0000-000000000004', 'UNREADABLE', null,
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
    clock_timestamp() - interval '2 seconds',
    clock_timestamp() - interval '1 second'
  );

select lives_ok(
  $$
    insert into public.confirmed_facts (id, candidate_fact_id, confirmation_id)
    values (
      '65000000-0000-0000-0000-000000000001',
      '63000000-0000-0000-0000-000000000001',
      '64000000-0000-0000-0000-000000000001'
    )
  $$,
  'an accepted confirmation derives one authoritative fact'
);

select is(
  (select value from public.confirmed_facts where id = '65000000-0000-0000-0000-000000000001'),
  '100'::jsonb,
  'accepted confirmation preserves the candidate value'
);

select lives_ok(
  $$
    insert into public.confirmed_facts (id, candidate_fact_id, confirmation_id)
    values (
      '65000000-0000-0000-0000-000000000002',
      '63000000-0000-0000-0000-000000000002',
      '64000000-0000-0000-0000-000000000002'
    )
  $$,
  'a corrected confirmation derives one authoritative fact'
);

select is(
  (select value from public.confirmed_facts where id = '65000000-0000-0000-0000-000000000002'),
  '250'::jsonb,
  'corrected confirmation uses only the corrected value'
);

select throws_ok(
  $$
    insert into public.confirmed_facts (id, candidate_fact_id, confirmation_id)
    values (
      '65000000-0000-0000-0000-000000000003',
      '63000000-0000-0000-0000-000000000003',
      '64000000-0000-0000-0000-000000000003'
    )
  $$,
  '23514',
  null,
  'ABSENT confirmation cannot create a confirmed fact'
);

select throws_ok(
  $$
    insert into public.confirmed_facts (id, candidate_fact_id, confirmation_id)
    values (
      '65000000-0000-0000-0000-000000000005',
      '63000000-0000-0000-0000-000000000004',
      '64000000-0000-0000-0000-000000000004'
    )
  $$,
  '23514',
  null,
  'UNREADABLE confirmation cannot create a confirmed fact'
);

select throws_ok(
  $$
    insert into public.confirmed_facts (
      id, candidate_fact_id, confirmation_id, field_key
    ) values (
      '65000000-0000-0000-0000-000000000004',
      '63000000-0000-0000-0000-000000000002',
      '64000000-0000-0000-0000-000000000002',
      'tampered.field'
    )
  $$,
  '23514',
  null,
  'caller-supplied authoritative fields must match candidate evidence'
);

select throws_ok(
  $$
    update public.confirmed_facts
    set value = '999'::jsonb
    where id = '65000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'confirmed fact authoritative fields are immutable'
);

select lives_ok(
  $$
    update public.confirmed_facts
    set stale_at = clock_timestamp()
    where id = '65000000-0000-0000-0000-000000000001'
  $$,
  'confirmed facts may only transition to stale without rewriting evidence'
);

select throws_ok(
  $$
    update public.page_regions
    set x = 0.25, width = 0.25
    where id = '62000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'confirmed source page coordinates are immutable'
);

select throws_ok(
  $$delete from public.page_regions where id = '62000000-0000-0000-0000-000000000001'$$,
  '42501',
  null,
  'confirmed source page regions cannot be deleted'
);

select throws_ok(
  $$
    update public.candidate_facts
    set field_key = 'tampered.field',
        proposed_value = '999'::jsonb,
        page_region_id = '62000000-0000-0000-0000-000000000002'
    where id = '63000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'candidate value, field, and provenance are immutable'
);

select lives_ok(
  $$
    update public.candidate_facts
    set stale_at = clock_timestamp()
    where id = '63000000-0000-0000-0000-000000000001'
  $$,
  'candidate stale_at is the only permitted mutation'
);

select throws_ok(
  $$delete from public.candidate_facts where id = '63000000-0000-0000-0000-000000000001'$$,
  '42501',
  null,
  'candidate facts cannot be deleted'
);

select throws_ok(
  $$
    update public.fact_confirmations
    set disposition = 'CORRECTED',
        corrected_value = '999'::jsonb,
        confirmed_at = confirmed_at + interval '1 second'
    where id = '64000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'confirmation disposition, correction, and time are immutable'
);

select throws_ok(
  $$
    delete from public.fact_confirmations
    where id = '64000000-0000-0000-0000-000000000001'
  $$,
  '42501',
  null,
  'fact confirmations cannot be deleted'
);

select throws_ok(
  $$
    insert into public.fact_confirmations (
      id, case_id, case_version, candidate_fact_id, disposition,
      actor_id, assigned_officer_id, authority_source,
      authority_granted_at, confirmed_at
    ) values (
      '64000000-0000-0000-0000-000000000005',
      '10000000-0000-0000-0000-000000000001', 1,
      '63000000-0000-0000-0000-000000000005', 'ACCEPTED',
      '00000000-0000-0000-0000-000000000002',
      '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
      clock_timestamp() - interval '500 milliseconds',
      clock_timestamp() - interval '100 milliseconds'
    )
  $$,
  '23514',
  null,
  'only the assigned officer actor may record a fact confirmation'
);

update public.case_assignments
set revoked_at = clock_timestamp() - interval '1 second'
where case_id = '10000000-0000-0000-0000-000000000001'
  and officer_id = '00000000-0000-0000-0000-000000000001';

select throws_ok(
  $$
    insert into public.fact_confirmations (
      id, case_id, case_version, candidate_fact_id, disposition,
      actor_id, assigned_officer_id, authority_source,
      authority_granted_at, confirmed_at
    ) values (
      '64000000-0000-0000-0000-000000000005',
      '10000000-0000-0000-0000-000000000001', 1,
      '63000000-0000-0000-0000-000000000005', 'ACCEPTED',
      '00000000-0000-0000-0000-000000000001',
      '00000000-0000-0000-0000-000000000001', 'SYNTHETIC_TEST',
      clock_timestamp() - interval '500 milliseconds',
      clock_timestamp() - interval '100 milliseconds'
    )
  $$,
  '23514',
  null,
  'a revoked assignment cannot authorize a later fact confirmation'
);

select * from finish();
rollback;
