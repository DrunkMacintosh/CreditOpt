begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, storage, pg_catalog;

select plan(9);

insert into storage.buckets (id, name, public)
values ('creditops-incoming', 'creditops-incoming', false)
on conflict (id) do update set public = excluded.public;

insert into public.credit_cases (id, case_version, workflow_state, created_by)
values (
  '10000000-0000-0000-0000-000000000001',
  1,
  'INTAKE_DRAFT',
  '00000000-0000-0000-0000-000000000001'
);

insert into public.case_assignments (case_id, officer_id, assigned_by)
values (
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000010'
);

insert into public.upload_intents (
  id,
  case_id,
  case_version,
  assigned_officer_id,
  bucket_id,
  object_key,
  original_filename,
  accepted_content_type,
  size_ceiling,
  declared_size_bytes,
  expires_at,
  created_at
)
values
  (
    '20000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    1,
    '00000000-0000-0000-0000-000000000001',
    'creditops-incoming',
    'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000001',
    'statement.pdf',
    'application/pdf',
    1048576,
    1048576,
    clock_timestamp() + interval '5 minutes',
    clock_timestamp()
  ),
  (
    '20000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    1,
    '00000000-0000-0000-0000-000000000001',
    'creditops-incoming',
    'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000002',
    'statement.pdf',
    'application/pdf',
    1048576,
    1048576,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '10 minutes'
  ),
  (
    '20000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000001',
    1,
    '00000000-0000-0000-0000-000000000001',
    'creditops-incoming',
    'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000003',
    'statement.pdf',
    'application/pdf',
    1048576,
    1048576,
    clock_timestamp() + interval '5 minutes',
    clock_timestamp()
  );

select is(
  (
    select count(*)
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname = 'creditops_insert_with_active_upload_intent'
      and cmd = 'INSERT'
  ),
  1::bigint,
  'Storage has one authenticated insert policy backed by upload intents'
);

select is(
  (
    select count(*)
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname like 'creditops_%'
      and cmd = 'UPDATE'
  ),
  0::bigint,
  'Storage exposes no CreditOps update policy, so authenticated upsert is unavailable'
);

set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  '00000000-0000-0000-0000-000000000001',
  true
);

select lives_ok(
  $$
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'creditops-incoming',
      'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000001',
      '00000000-0000-0000-0000-000000000001'
    )
  $$,
  'the assigned officer can upload to the exact active-intent path'
);

-- storage.objects exposes an INSERT and a SELECT policy but deliberately no
-- UPDATE policy, so an authenticated UPDATE matches zero rows and mutates
-- nothing — a no-op denial rather than a privilege error.  (The now-existing
-- object row means this is a real RLS test; before the upload_intents grant
-- fix the insert failed and this update trivially matched nothing.)  The
-- update runs as a top-level statement — a data-modifying CTE may not be
-- nested inside the is() subquery — then the assertion proves nothing changed.
update storage.objects
set metadata = '{"attempted_upsert": true}'::jsonb
where bucket_id = 'creditops-incoming'
  and name = 'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000001';

select is(
  (
    select metadata ->> 'attempted_upsert'
    from storage.objects
    where bucket_id = 'creditops-incoming'
      and name = 'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000001'
  ),
  null,
  'authenticated object update changes no row: RLS exposes no update policy'
);

select throws_ok(
  $$
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'creditops-incoming',
      'incoming/10000000-0000-0000-0000-000000000001/not-the-intent',
      '00000000-0000-0000-0000-000000000001'
    )
  $$,
  '42501',
  null,
  'the assigned officer cannot upload outside an active intent path'
);

select set_config(
  'request.jwt.claim.sub',
  '00000000-0000-0000-0000-000000000002',
  true
);

select throws_ok(
  $$
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'creditops-incoming',
      'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000001',
      '00000000-0000-0000-0000-000000000002'
    )
  $$,
  '42501',
  null,
  'another officer cannot use the upload intent'
);

select set_config(
  'request.jwt.claim.sub',
  '00000000-0000-0000-0000-000000000001',
  true
);

select throws_ok(
  $$
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'creditops-incoming',
      'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000002',
      '00000000-0000-0000-0000-000000000001'
    )
  $$,
  '42501',
  null,
  'an expired upload intent cannot authorize a Storage insert'
);

reset role;
update public.case_assignments
set revoked_at = clock_timestamp()
where case_id = '10000000-0000-0000-0000-000000000001';

set local role authenticated;
select set_config(
  'request.jwt.claim.sub',
  '00000000-0000-0000-0000-000000000001',
  true
);

select is(
  (select count(*) from public.upload_intents),
  0::bigint,
  'revoking the case assignment removes upload-intent visibility'
);

select throws_ok(
  $$
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'creditops-incoming',
      'incoming/10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000003',
      '00000000-0000-0000-0000-000000000001'
    )
  $$,
  '42501',
  null,
  'a live intent cannot authorize upload after assignment revocation'
);

select * from finish();
rollback;
