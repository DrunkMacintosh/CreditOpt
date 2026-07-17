do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'creditops_api') then
    create role creditops_api nologin nobypassrls;
  end if;
end;
$$;

alter role creditops_api nologin nobypassrls;
grant creditops_api to service_role;

grant usage on schema public, auth to creditops_api;
grant execute on function auth.uid() to creditops_api;

create or replace function public.api_actor_created_case(target_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog
as $$
  select exists (
    select 1
    from public.credit_cases
    where id = target_case_id
      and created_by = (select auth.uid())
  );
$$;

revoke all on function public.api_actor_created_case(uuid) from public;
grant execute on function public.api_actor_created_case(uuid) to creditops_api;

grant select, insert on
  public.credit_cases,
  public.case_assignments,
  public.financing_requests,
  public.audit_events
to creditops_api;

create policy credit_cases_api_select
on public.credit_cases
for select
to creditops_api
using (
  exists (
    select 1
    from public.case_assignments as assignment
    where assignment.case_id = credit_cases.id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

create policy credit_cases_api_insert
on public.credit_cases
for insert
to creditops_api
with check (created_by = (select auth.uid()));

create policy case_assignments_api_select
on public.case_assignments
for select
to creditops_api
using (
  officer_id = (select auth.uid())
  and revoked_at is null
);

create policy case_assignments_api_insert
on public.case_assignments
for insert
to creditops_api
with check (
  officer_id = (select auth.uid())
  and assigned_by = (select auth.uid())
  and revoked_at is null
  and public.api_actor_created_case(case_assignments.case_id)
);

create policy financing_requests_api_select
on public.financing_requests
for select
to creditops_api
using (
  exists (
    select 1
    from public.case_assignments as assignment
    where assignment.case_id = financing_requests.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

create policy financing_requests_api_insert
on public.financing_requests
for insert
to creditops_api
with check (
  created_by = (select auth.uid())
  and exists (
    select 1
    from public.case_assignments as assignment
    where assignment.case_id = financing_requests.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

create policy audit_events_api_select
on public.audit_events
for select
to creditops_api
using (
  exists (
    select 1
    from public.case_assignments as assignment
    where assignment.case_id = audit_events.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);

create policy audit_events_api_insert
on public.audit_events
for insert
to creditops_api
with check (
  actor_type = 'HUMAN'
  and actor_id = (select auth.uid())
  and exists (
    select 1
    from public.case_assignments as assignment
    where assignment.case_id = audit_events.case_id
      and assignment.officer_id = (select auth.uid())
      and assignment.revoked_at is null
  )
);
